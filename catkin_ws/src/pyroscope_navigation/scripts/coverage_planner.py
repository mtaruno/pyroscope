#!/usr/bin/env python

"""
Costmap-aware coverage planner for Pyroscope.

This node does not precommit to a blind lawnmower list. It samples the live
global costmap inside the requested square, keeps only safe free-space targets,
and then repeatedly chooses the next uncovered target that has the shortest
reachable plan from the robot's current pose.
"""

import math

import actionlib
import rospy
import tf
from geometry_msgs.msg import PoseStamped
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from nav_msgs.msg import OccupancyGrid
from nav_msgs.srv import GetPlan
from std_msgs.msg import Bool, Int32, String


WALL_MARGIN = 0.30  # meters


class CoverageTarget(object):
    def __init__(self, target_id, x, y, row, col):
        self.target_id = target_id
        self.x = x
        self.y = y
        self.row = row
        self.col = col
        self.covered = False
        self.skipped = False
        self.failures = 0
        self.currently_safe = True


class CoveragePlanner(object):
    def __init__(self):
        rospy.init_node('coverage_planner', anonymous=False)

        # Mission geometry
        self.area_width = rospy.get_param('~area_width', 10.0)
        self.area_height = rospy.get_param('~area_height', 10.0)
        self.row_spacing = rospy.get_param('~row_spacing', 1.0)
        self.waypoint_spacing = rospy.get_param('~waypoint_spacing', 1.0)
        self.origin_x = rospy.get_param('~origin_x', 0.0)
        self.origin_y = rospy.get_param('~origin_y', 0.0)
        self.wall_margin = rospy.get_param('~wall_margin', WALL_MARGIN)

        # Timing and planning
        self.dwell_time = rospy.get_param('~dwell_time', 3.0)
        self.waypoint_timeout = rospy.get_param('~waypoint_timeout', 60.0)
        self.pose_stale_timeout = rospy.get_param('~pose_stale_timeout', 0.75)
        self.costmap_stale_timeout = rospy.get_param('~costmap_stale_timeout', 2.0)
        self.make_plan_tolerance = rospy.get_param('~make_plan_tolerance', 0.10)

        # Coverage target safety
        self.target_cost_threshold = int(rospy.get_param('~target_cost_threshold', 40))
        self.target_check_radius = rospy.get_param('~target_check_radius', 0.16)
        self.max_target_failures = int(rospy.get_param('~max_target_failures', 2))
        self.failure_penalty = rospy.get_param('~failure_penalty', 0.75)
        self.row_change_penalty = rospy.get_param('~row_change_penalty', 0.10)

        # State
        self.targets = []
        self.target_lookup = {}
        self.next_target_id = 0
        self.latest_costmap = None
        self.latest_costmap_stamp = None
        self.last_selected_row = None

        # Publishers
        self.capture_ready_pub = rospy.Publisher('/coverage/capture_ready', Bool, queue_size=1)
        self.progress_pub = rospy.Publisher('/coverage/progress', String, queue_size=1, latch=True)
        self.total_points_pub = rospy.Publisher('/coverage/total_points', Int32, queue_size=1, latch=True)
        self.complete_pub = rospy.Publisher('/coverage/complete', Bool, queue_size=1, latch=True)

        # Subscribers
        self.costmap_sub = rospy.Subscriber(
            '/move_base/global_costmap/costmap',
            OccupancyGrid,
            self.costmap_callback,
            queue_size=1,
        )

        # move_base interfaces
        self.tf_listener = tf.TransformListener()
        self.move_base_client = actionlib.SimpleActionClient('move_base', MoveBaseAction)
        self.make_plan_srv = None
        self.clear_costmaps_srv = None

        self.complete_pub.publish(Bool(data=False))
        self.total_points_pub.publish(Int32(data=0))
        self.progress_pub.publish(String(data='Waiting for costmap...'))

        rospy.loginfo("Waiting for move_base action server...")
        if not self.move_base_client.wait_for_server(rospy.Duration(30.0)):
            rospy.logfatal("move_base action server not available -- aborting")
            rospy.signal_shutdown("move_base unavailable")
            return

        try:
            rospy.wait_for_service('/move_base/make_plan', timeout=5.0)
            self.make_plan_srv = rospy.ServiceProxy('/move_base/make_plan', GetPlan)
            rospy.loginfo("Connected to /move_base/make_plan")
        except rospy.ROSException:
            rospy.logwarn("/move_base/make_plan not available; planner will fall back to Euclidean ordering")

        try:
            from std_srvs.srv import Empty
            rospy.wait_for_service('/move_base/clear_costmaps', timeout=2.0)
            self.clear_costmaps_srv = rospy.ServiceProxy('/move_base/clear_costmaps', Empty)
        except Exception:
            self.clear_costmaps_srv = None

        rospy.loginfo("Coverage planner configured")
        rospy.loginfo("  Area: %.2f x %.2f m centered at (%.2f, %.2f)",
                      self.area_width, self.area_height, self.origin_x, self.origin_y)
        rospy.loginfo("  Sampling: row_spacing=%.2f m waypoint_spacing=%.2f m",
                      self.row_spacing, self.waypoint_spacing)
        rospy.loginfo("  Safety: wall_margin=%.2f m target_cost_threshold=%d target_check_radius=%.2f m",
                      self.wall_margin, self.target_cost_threshold, self.target_check_radius)

    def costmap_callback(self, msg):
        self.latest_costmap = msg
        if msg.header.stamp != rospy.Time():
            self.latest_costmap_stamp = msg.header.stamp
        else:
            self.latest_costmap_stamp = rospy.Time.now()

    def get_robot_pose(self):
        try:
            common_time = self.tf_listener.getLatestCommonTime('odom', 'base_link')
            trans, rot = self.tf_listener.lookupTransform('odom', 'base_link', rospy.Time(0))
            yaw = tf.transformations.euler_from_quaternion(rot)[2]
            pose_age = abs((rospy.Time.now() - common_time).to_sec())
            return (trans[0], trans[1], yaw, pose_age)
        except (tf.Exception, tf.LookupException, tf.ConnectivityException, tf.ExtrapolationException):
            return None

    def wait_for_fresh_pose(self, timeout):
        deadline = rospy.Time.now() + rospy.Duration(timeout)
        rate = rospy.Rate(10)
        while rospy.Time.now() < deadline and not rospy.is_shutdown():
            pose = self.get_robot_pose()
            if pose is not None and pose[3] <= self.pose_stale_timeout:
                return True
            rate.sleep()
        return False

    def get_costmap_age(self):
        if self.latest_costmap_stamp is None:
            return None
        return abs((rospy.Time.now() - self.latest_costmap_stamp).to_sec())

    def wait_for_costmap(self, timeout):
        deadline = rospy.Time.now() + rospy.Duration(timeout)
        rate = rospy.Rate(10)
        while rospy.Time.now() < deadline and not rospy.is_shutdown():
            if self.latest_costmap is not None:
                age = self.get_costmap_age()
                if age is not None and age <= self.costmap_stale_timeout:
                    return True
            rate.sleep()
        return False

    def build_pose(self, x, y, yaw):
        pose = PoseStamped()
        pose.header.frame_id = 'odom'
        pose.header.stamp = rospy.Time.now()
        pose.pose.position.x = x
        pose.pose.position.y = y
        pose.pose.position.z = 0.0
        quat = tf.transformations.quaternion_from_euler(0.0, 0.0, yaw)
        pose.pose.orientation.x = quat[0]
        pose.pose.orientation.y = quat[1]
        pose.pose.orientation.z = quat[2]
        pose.pose.orientation.w = quat[3]
        return pose

    def axis_points(self, min_value, max_value, spacing):
        points = []
        value = min_value
        while value <= max_value + 1e-6:
            points.append(min(value, max_value))
            value += spacing
        if not points:
            points = [min_value]
        elif abs(points[-1] - max_value) > 1e-6:
            points.append(max_value)

        deduped = []
        for point in points:
            if not deduped or abs(point - deduped[-1]) > 1e-6:
                deduped.append(point)
        return deduped

    def world_to_costmap(self, x, y):
        if self.latest_costmap is None:
            return None

        info = self.latest_costmap.info
        mx = int(math.floor((x - info.origin.position.x) / info.resolution))
        my = int(math.floor((y - info.origin.position.y) / info.resolution))

        if mx < 0 or my < 0 or mx >= info.width or my >= info.height:
            return None
        return (mx, my)

    def costmap_cell(self, mx, my):
        info = self.latest_costmap.info
        if mx < 0 or my < 0 or mx >= info.width or my >= info.height:
            return None
        return self.latest_costmap.data[my * info.width + mx]

    def is_target_safe(self, x, y):
        if self.latest_costmap is None:
            return False
        costmap_age = self.get_costmap_age()
        if costmap_age is None or costmap_age > self.costmap_stale_timeout:
            return False

        center = self.world_to_costmap(x, y)
        if center is None:
            return False

        info = self.latest_costmap.info
        radius_cells = int(math.ceil(self.target_check_radius / info.resolution))
        mx, my = center

        for cx in range(mx - radius_cells, mx + radius_cells + 1):
            for cy in range(my - radius_cells, my + radius_cells + 1):
                cost = self.costmap_cell(cx, cy)
                if cost is None or cost < 0:
                    return False
                if cost >= self.target_cost_threshold:
                    return False
        return True

    def refresh_targets_from_costmap(self):
        previous_total = self.count_total_targets()
        previous_pending = self.count_pending_targets()

        min_x = self.origin_x - self.area_width / 2.0 + self.wall_margin
        max_x = self.origin_x + self.area_width / 2.0 - self.wall_margin
        min_y = self.origin_y - self.area_height / 2.0 + self.wall_margin
        max_y = self.origin_y + self.area_height / 2.0 - self.wall_margin

        if max_x <= min_x or max_y <= min_y:
            rospy.logwarn_throttle(5.0, "Area too small after wall margin; using center point fallback")
            key = (0, 0)
            target = self.target_lookup.get(key)
            if target is None and self.is_target_safe(self.origin_x, self.origin_y):
                target = CoverageTarget(self.next_target_id, self.origin_x, self.origin_y, 0, 0)
                self.next_target_id += 1
                self.target_lookup[key] = target
            if target is not None:
                target.currently_safe = self.is_target_safe(self.origin_x, self.origin_y)
                target.x = self.origin_x
                target.y = self.origin_y
            self.targets = sorted(self.target_lookup.values(), key=lambda existing: (existing.row, existing.col))
            return

        x_points = self.axis_points(min_x, max_x, self.waypoint_spacing)
        y_points = self.axis_points(min_y, max_y, self.row_spacing)

        for row_index, y in enumerate(y_points):
            for col_index, x in enumerate(x_points):
                key = (row_index, col_index)
                currently_safe = self.is_target_safe(x, y)
                target = self.target_lookup.get(key)

                if target is None:
                    if not currently_safe:
                        continue
                    target = CoverageTarget(self.next_target_id, x, y, row_index, col_index)
                    self.next_target_id += 1
                    self.target_lookup[key] = target

                target.x = x
                target.y = y
                target.currently_safe = currently_safe

        self.targets = sorted(self.target_lookup.values(), key=lambda target: (target.row, target.col))

        current_total = self.count_total_targets()
        current_pending = self.count_pending_targets()
        if current_total != previous_total or current_pending != previous_pending:
            rospy.loginfo(
                "Coverage target set refreshed: total=%d pending=%d covered=%d skipped=%d",
                current_total,
                current_pending,
                self.count_covered_targets(),
                self.count_skipped_targets(),
            )

    def count_known_targets(self):
        return len(self.targets)

    def count_total_targets(self):
        return len([target for target in self.targets if not target.skipped])

    def count_covered_targets(self):
        return len([target for target in self.targets if target.covered])

    def count_pending_targets(self):
        return len([target for target in self.targets if not target.covered and not target.skipped])

    def count_active_targets(self):
        return len([
            target for target in self.targets
            if not target.covered and not target.skipped and target.currently_safe
        ])

    def count_skipped_targets(self):
        return len([target for target in self.targets if target.skipped])

    def publish_total_points(self):
        self.total_points_pub.publish(Int32(data=self.count_total_targets()))

    def publish_progress(self):
        covered = self.count_covered_targets()
        total = self.count_total_targets()
        skipped = self.count_skipped_targets()
        active = self.count_active_targets()
        if total > 0:
            percent = int(round((100.0 * covered) / total))
        else:
            percent = 100
        message = "%d/%d targets covered (%d%%, %d skipped, %d active)" % (
            covered,
            total,
            percent,
            skipped,
            active,
        )
        self.progress_pub.publish(String(data=message))

    def path_length(self, poses):
        if not poses:
            return None
        total = 0.0
        for i in range(1, len(poses)):
            p0 = poses[i - 1].pose.position
            p1 = poses[i].pose.position
            total += math.sqrt((p1.x - p0.x) ** 2 + (p1.y - p0.y) ** 2)
        return total

    def plan_length_to_target(self, start_pose, target):
        if self.make_plan_srv is None:
            dx = target.x - start_pose.pose.position.x
            dy = target.y - start_pose.pose.position.y
            return math.sqrt(dx ** 2 + dy ** 2)

        goal = self.build_pose(target.x, target.y, 0.0)
        try:
            response = self.make_plan_srv(start_pose, goal, self.make_plan_tolerance)
        except rospy.ServiceException:
            return None

        if not response.plan.poses:
            return None
        return self.path_length(response.plan.poses)

    def choose_next_target_once(self):
        self.refresh_targets_from_costmap()

        pose = self.get_robot_pose()
        if pose is None or pose[3] > self.pose_stale_timeout:
            rospy.logwarn("Robot pose is stale while selecting the next coverage target")
            return None

        start_pose = self.build_pose(pose[0], pose[1], pose[2])
        best_target = None
        best_score = None

        pending = [
            target for target in self.targets
            if not target.covered and not target.skipped and target.currently_safe
        ]
        pending.sort(key=lambda target: math.sqrt((target.x - pose[0]) ** 2 + (target.y - pose[1]) ** 2))

        for target in pending:
            plan_length = self.plan_length_to_target(start_pose, target)
            if plan_length is None:
                continue

            row_penalty = 0.0
            if self.last_selected_row is not None and target.row != self.last_selected_row:
                row_penalty = abs(target.row - self.last_selected_row) * self.row_change_penalty

            score = plan_length + (target.failures * self.failure_penalty) + row_penalty
            if best_score is None or score < best_score:
                best_score = score
                best_target = target

        return best_target

    def choose_next_target(self):
        target = self.choose_next_target_once()
        if target is not None:
            return target

        if self.clear_costmaps_srv is not None:
            try:
                rospy.logwarn("No reachable target found; clearing costmaps and retrying once")
                self.clear_costmaps_srv()
                rospy.sleep(1.0)
            except Exception:
                pass
            return self.choose_next_target_once()

        return None

    def send_move_base_goal(self, target):
        pose = self.get_robot_pose()
        if pose is None or pose[3] > self.pose_stale_timeout:
            rospy.logwarn("Robot pose is stale before goal dispatch")
            return False

        if not target.currently_safe or not self.is_target_safe(target.x, target.y):
            rospy.logwarn("Target %d at (%.2f, %.2f) is no longer safe before dispatch",
                          target.target_id, target.x, target.y)
            target.currently_safe = False
            return False

        goal_yaw = math.atan2(target.y - pose[1], target.x - pose[0])

        goal = MoveBaseGoal()
        goal.target_pose.header.frame_id = 'odom'
        goal.target_pose.header.stamp = rospy.Time.now()
        goal.target_pose.pose.position.x = target.x
        goal.target_pose.pose.position.y = target.y
        goal.target_pose.pose.position.z = 0.0

        quat = tf.transformations.quaternion_from_euler(0.0, 0.0, goal_yaw)
        goal.target_pose.pose.orientation.x = quat[0]
        goal.target_pose.pose.orientation.y = quat[1]
        goal.target_pose.pose.orientation.z = quat[2]
        goal.target_pose.pose.orientation.w = quat[3]

        self.move_base_client.send_goal(goal)
        finished = self.move_base_client.wait_for_result(rospy.Duration(self.waypoint_timeout))

        if not finished:
            self.move_base_client.cancel_goal()
            rospy.logwarn("move_base timed out reaching target %d at (%.2f, %.2f)",
                          target.target_id, target.x, target.y)
            return False

        state = self.move_base_client.get_state()
        if state == actionlib.GoalStatus.SUCCEEDED:
            return True

        rospy.logwarn("move_base failed for target %d at (%.2f, %.2f) -- state %d",
                      target.target_id, target.x, target.y, state)
        return False

    def capture_target(self):
        rospy.loginfo("Dwelling for %.1f s and triggering capture", self.dwell_time)
        self.capture_ready_pub.publish(Bool(data=True))
        rospy.sleep(self.dwell_time)
        self.capture_ready_pub.publish(Bool(data=False))

    def complete_mission(self):
        covered = self.count_covered_targets()
        skipped = self.count_skipped_targets()
        total = self.count_total_targets()
        rospy.loginfo("Coverage mission complete: covered=%d total=%d skipped=%d", covered, total, skipped)
        self.publish_total_points()
        self.publish_progress()
        self.complete_pub.publish(Bool(data=True))
        rospy.sleep(1.0)

    def run(self):
        rospy.loginfo("Waiting for a fresh robot pose...")
        if not self.wait_for_fresh_pose(10.0):
            rospy.logfatal("No fresh robot pose available; aborting coverage mission")
            self.complete_pub.publish(Bool(data=True))
            return

        rospy.loginfo("Waiting for the global costmap to populate...")
        if not self.wait_for_costmap(10.0):
            rospy.logfatal("No fresh global costmap available; aborting coverage mission")
            self.complete_pub.publish(Bool(data=True))
            return

        rospy.sleep(1.0)
        self.refresh_targets_from_costmap()
        self.publish_total_points()
        self.publish_progress()

        if self.count_known_targets() == 0:
            rospy.logwarn("No safe coverage targets found inside the requested square")
            self.complete_mission()
            return

        while not rospy.is_shutdown():
            self.refresh_targets_from_costmap()
            self.publish_total_points()
            self.publish_progress()

            if self.count_pending_targets() == 0:
                break

            target = self.choose_next_target()
            if target is None:
                rospy.logwarn("No remaining reachable coverage targets; ending mission")
                for pending in self.targets:
                    if not pending.covered and not pending.skipped:
                        pending.skipped = True
                self.publish_total_points()
                self.publish_progress()
                break

            rospy.loginfo("Selected target %d at (%.2f, %.2f) row=%d col=%d failures=%d",
                          target.target_id, target.x, target.y,
                          target.row, target.col, target.failures)

            success = self.send_move_base_goal(target)
            if success:
                target.covered = True
                self.last_selected_row = target.row
                self.publish_progress()
                self.capture_target()
            else:
                target.failures += 1
                if target.failures >= self.max_target_failures:
                    target.skipped = True
                    self.publish_total_points()
                    rospy.logwarn("Skipping target %d after %d failures",
                                  target.target_id, self.max_target_failures)
                self.publish_progress()

        self.complete_mission()


if __name__ == '__main__':
    try:
        planner = CoveragePlanner()
        planner.run()
    except rospy.ROSInterruptException:
        pass
