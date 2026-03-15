#!/usr/bin/env python2

"""
Coverage Path Planner for Pyroscope
Generates a boustrophedon (lawnmower) pattern over a rectangular area
and sends waypoints to move_base for execution with obstacle avoidance.
Pauses at each waypoint for thermal camera capture.
"""

import rospy
import math
import actionlib
import tf
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from geometry_msgs.msg import Twist
from nav_msgs.msg import OccupancyGrid
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Bool, String


# Margin inset from area boundary so waypoints never land on walls.
# Must be >= robot half-width (0.125m) + inflation_radius (0.15m).
WALL_MARGIN = 0.30  # meters - must be > robot_half_width (0.125m) + inflation_radius (0.12m)


class CoveragePlanner:
    def __init__(self):
        rospy.init_node('coverage_planner', anonymous=False)

        # Area parameters
        self.area_width = rospy.get_param('~area_width', 10.0)
        self.area_height = rospy.get_param('~area_height', 10.0)
        self.row_spacing = rospy.get_param('~row_spacing', 1.0)
        self.waypoint_spacing = rospy.get_param('~waypoint_spacing', 1.0)
        self.origin_x = rospy.get_param('~origin_x', 0.0)
        self.origin_y = rospy.get_param('~origin_y', 0.0)

        # Timing parameters
        self.dwell_time = rospy.get_param('~dwell_time', 3.0)
        self.waypoint_timeout = rospy.get_param('~waypoint_timeout', 60.0)
        self.max_waypoint_failures = int(rospy.get_param('~max_waypoint_failures', 3))
        self.pose_stale_timeout = rospy.get_param('~pose_stale_timeout', 0.75)
        self.scan_stale_timeout = rospy.get_param('~scan_stale_timeout', 1.0)
        self.costmap_stale_timeout = rospy.get_param('~costmap_stale_timeout', 2.0)

        # Recovery parameters
        self.recovery_turn_speed = rospy.get_param('~recovery_turn_speed', 0.7)
        self.recovery_turn_angle = rospy.get_param('~recovery_turn_angle', 1.0)
        self.recovery_backup_speed = rospy.get_param('~recovery_backup_speed', -0.12)
        self.recovery_backup_distance = rospy.get_param('~recovery_backup_distance', 0.35)
        self.recovery_clearance = rospy.get_param('~recovery_clearance', 0.30)
        self.waypoint_validation_radius = rospy.get_param('~waypoint_validation_radius', 0.18)
        self.waypoint_cost_threshold = int(rospy.get_param('~waypoint_cost_threshold', 253))
        self.scan_blocked_margin = rospy.get_param('~scan_blocked_margin', 2.0)
        self.scan_blocked_sector = rospy.get_param('~scan_blocked_sector', 0.20)

        # State
        self.waypoints = []
        self.current_index = 0
        self.latest_scan = None
        self.latest_scan_stamp = None
        self.latest_costmap = None
        self.latest_costmap_stamp = None

        # Publishers
        self.cmd_vel_pub = rospy.Publisher('/cmd_vel', Twist, queue_size=1)
        self.capture_ready_pub = rospy.Publisher('/coverage/capture_ready', Bool, queue_size=1)
        self.progress_pub = rospy.Publisher('/coverage/progress', String, queue_size=1)
        self.complete_pub = rospy.Publisher('/coverage/complete', Bool, queue_size=1)
        self.scan_sub = rospy.Subscriber('/scan', LaserScan, self.scan_callback, queue_size=1)
        self.costmap_sub = rospy.Subscriber('/move_base/global_costmap/costmap', OccupancyGrid, self.costmap_callback, queue_size=1)
        self.tf_listener = tf.TransformListener()

        # move_base action client
        self.move_base_client = actionlib.SimpleActionClient('move_base', MoveBaseAction)
        rospy.loginfo("Waiting for move_base action server...")
        if not self.move_base_client.wait_for_server(rospy.Duration(30.0)):
            rospy.logfatal("move_base action server not available -- aborting")
            rospy.signal_shutdown("move_base unavailable")
            return

        rospy.loginfo("Connected to move_base action server")

        # Generate waypoints
        self.generate_waypoints()
        self.validate_waypoint_distances()

        rospy.loginfo("Coverage Planner initialized")
        rospy.loginfo("  Area: %.1f x %.1f m (margin: %.2fm from walls)",
                      self.area_width, self.area_height, WALL_MARGIN)
        rospy.loginfo("  Row spacing: %.1f m, Waypoint spacing: %.1f m",
                      self.row_spacing, self.waypoint_spacing)
        rospy.loginfo("  Origin: (%.1f, %.1f)", self.origin_x, self.origin_y)
        rospy.loginfo("  Total waypoints: %d", len(self.waypoints))
        rospy.loginfo("  Dwell time: %.1f s", self.dwell_time)
        rospy.loginfo("  Max retries per waypoint: %d", self.max_waypoint_failures)

    def generate_waypoints(self):
        """Generate boustrophedon (lawnmower) waypoints with wall margin inset."""
        self.waypoints = []

        # Center the grid on the origin, then inset by wall margin
        min_x = self.origin_x - self.area_width / 2.0 + WALL_MARGIN
        max_x = self.origin_x + self.area_width / 2.0 - WALL_MARGIN
        min_y = self.origin_y - self.area_height / 2.0 + WALL_MARGIN
        max_y = self.origin_y + self.area_height / 2.0 - WALL_MARGIN

        # If the area is too small for any margin, just use the center
        if max_x <= min_x or max_y <= min_y:
            cx = self.origin_x + self.area_width / 2.0
            cy = self.origin_y + self.area_height / 2.0
            self.waypoints.append((cx, cy))
            rospy.logwarn("Area too small for margin -- using center point only (%.2f, %.2f)", cx, cy)
            return

        effective_width = max_x - min_x
        effective_height = max_y - min_y

        num_rows = max(1, int(math.ceil(effective_height / self.row_spacing)) + 1)
        num_cols = max(1, int(math.ceil(effective_width / self.waypoint_spacing)) + 1)

        for row in range(num_rows):
            y = min_y + row * self.row_spacing
            if y > max_y:
                y = max_y

            # Alternate direction for lawnmower pattern
            if row % 2 == 0:
                col_range = range(num_cols)
            else:
                col_range = range(num_cols - 1, -1, -1)

            for col in col_range:
                x = min_x + col * self.waypoint_spacing
                if x > max_x:
                    x = max_x

                self.waypoints.append((x, y))

        rospy.loginfo("Generated %d waypoints in %d rows (inset %.2fm from walls)",
                      len(self.waypoints), num_rows, WALL_MARGIN)

    def validate_waypoint_distances(self):
        """Warn if consecutive waypoints exceed global costmap range"""
        costmap_half = 7.5  # half of 15m rolling window
        for i in range(1, len(self.waypoints)):
            x0, y0 = self.waypoints[i - 1]
            x1, y1 = self.waypoints[i]
            dist = math.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2)
            if dist > costmap_half:
                rospy.logwarn(
                    "Waypoints %d->%d are %.1fm apart (exceeds %.1fm costmap radius) "
                    "-- move_base may fail to plan",
                    i, i + 1, dist, costmap_half
                )

    def scan_callback(self, msg):
        self.latest_scan = msg
        self.latest_scan_stamp = msg.header.stamp if msg.header.stamp != rospy.Time() else rospy.Time.now()

    def costmap_callback(self, msg):
        self.latest_costmap = msg
        self.latest_costmap_stamp = msg.header.stamp if msg.header.stamp != rospy.Time() else rospy.Time.now()

    def stop_robot(self):
        self.cmd_vel_pub.publish(Twist())

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

    def get_scan_age(self):
        if self.latest_scan_stamp is None:
            return None
        return abs((rospy.Time.now() - self.latest_scan_stamp).to_sec())

    def get_costmap_age(self):
        if self.latest_costmap_stamp is None:
            return None
        return abs((rospy.Time.now() - self.latest_costmap_stamp).to_sec())

    def normalize_angle(self, angle):
        return math.atan2(math.sin(angle), math.cos(angle))

    def angle_in_sector(self, angle, start, end):
        angle = self.normalize_angle(angle)
        start = self.normalize_angle(start)
        end = self.normalize_angle(end)
        if start <= end:
            return start <= angle <= end
        return angle >= start or angle <= end

    def sector_clearance(self, start_angle, end_angle):
        if self.latest_scan is None:
            return None

        values = []
        angle = self.latest_scan.angle_min
        for distance in self.latest_scan.ranges:
            if self.angle_in_sector(angle, start_angle, end_angle):
                if math.isinf(distance):
                    values.append(self.latest_scan.range_max)
                elif not math.isnan(distance):
                    values.append(distance)
            angle += self.latest_scan.angle_increment

        return min(values) if values else None

    def choose_turn_direction(self):
        left_clearance = self.sector_clearance(math.radians(20), math.radians(110))
        right_clearance = self.sector_clearance(math.radians(-110), math.radians(-20))

        if left_clearance is None and right_clearance is None:
            return 1.0
        if right_clearance is None:
            return 1.0
        if left_clearance is None:
            return -1.0
        return 1.0 if left_clearance >= right_clearance else -1.0

    def costmap_cell(self, mx, my):
        info = self.latest_costmap.info
        if mx < 0 or my < 0 or mx >= info.width or my >= info.height:
            return None
        return self.latest_costmap.data[my * info.width + mx]

    def world_to_costmap(self, x, y):
        if self.latest_costmap is None:
            return None

        info = self.latest_costmap.info
        mx = int(math.floor((x - info.origin.position.x) / info.resolution))
        my = int(math.floor((y - info.origin.position.y) / info.resolution))
        if mx < 0 or my < 0 or mx >= info.width or my >= info.height:
            return None
        return mx, my

    def waypoint_cost_invalid(self, x, y):
        costmap_age = self.get_costmap_age()
        if self.latest_costmap is None or costmap_age is None or costmap_age > self.costmap_stale_timeout:
            return False

        center = self.world_to_costmap(x, y)
        if center is None:
            return False

        mx, my = center
        radius_cells = int(math.ceil(self.waypoint_validation_radius / self.latest_costmap.info.resolution))

        for cx in range(mx - radius_cells, mx + radius_cells + 1):
            for cy in range(my - radius_cells, my + radius_cells + 1):
                cost = self.costmap_cell(cx, cy)
                if cost is None:
                    continue
                if cost < 0 or cost >= self.waypoint_cost_threshold:
                    rospy.logwarn(
                        "Skipping waypoint (%.2f, %.2f): costmap cell %d near target exceeds threshold %d",
                        x, y, cost, self.waypoint_cost_threshold
                    )
                    return True

        return False

    def waypoint_scan_blocked(self, x, y):
        pose = self.get_robot_pose()
        scan_age = self.get_scan_age()
        if pose is None or scan_age is None or scan_age > self.scan_stale_timeout:
            return False

        dx = x - pose[0]
        dy = y - pose[1]
        target_distance = math.sqrt(dx ** 2 + dy ** 2)
        if target_distance <= 0.05:
            return False

        target_bearing = self.normalize_angle(math.atan2(dy, dx) - pose[2])
        clearance = self.sector_clearance(
            target_bearing - self.scan_blocked_sector,
            target_bearing + self.scan_blocked_sector
        )
        if clearance is None:
            return False

        if clearance + self.scan_blocked_margin < target_distance:
            rospy.logwarn(
                "Skipping waypoint (%.2f, %.2f): scan shows obstacle at %.2fm before target distance %.2fm",
                x, y, clearance, target_distance
            )
            return True

        return False

    def waypoint_is_valid(self, x, y):
        if self.waypoint_cost_invalid(x, y):
            return False
        if self.waypoint_scan_blocked(x, y):
            return False
        return True

    def rotate_for_recovery(self, turn_direction):
        cmd = Twist()
        cmd.angular.z = turn_direction * abs(self.recovery_turn_speed)

        pose = self.get_robot_pose()
        if pose is not None and pose[3] <= self.pose_stale_timeout:
            start_yaw = pose[2]
            timeout = rospy.Time.now() + rospy.Duration(4.0)
            rate = rospy.Rate(15)
            while not rospy.is_shutdown() and rospy.Time.now() < timeout:
                pose = self.get_robot_pose()
                if pose is None:
                    break
                yaw_delta = abs(self.normalize_angle(pose[2] - start_yaw))
                if yaw_delta >= self.recovery_turn_angle:
                    break
                self.cmd_vel_pub.publish(cmd)
                rate.sleep()
        else:
            duration = self.recovery_turn_angle / max(abs(self.recovery_turn_speed), 0.1)
            end_time = rospy.Time.now() + rospy.Duration(duration)
            rate = rospy.Rate(15)
            while not rospy.is_shutdown() and rospy.Time.now() < end_time:
                self.cmd_vel_pub.publish(cmd)
                rate.sleep()

        self.stop_robot()

    def backup_for_recovery(self):
        cmd = Twist()
        cmd.linear.x = min(self.recovery_backup_speed, -0.05)
        pose = self.get_robot_pose()
        target_distance = abs(self.recovery_backup_distance)

        if pose is not None and pose[3] <= self.pose_stale_timeout:
            start_x = pose[0]
            start_y = pose[1]
            timeout = rospy.Time.now() + rospy.Duration(6.0)
            rate = rospy.Rate(15)
            while not rospy.is_shutdown() and rospy.Time.now() < timeout:
                scan_age = self.get_scan_age()
                rear_clearance = self.sector_clearance(math.radians(140), math.radians(-140))
                if scan_age is not None and scan_age <= self.scan_stale_timeout and rear_clearance is not None and rear_clearance < self.recovery_clearance:
                    rospy.logwarn("Stopping recovery backup early -- rear clearance only %.2fm", rear_clearance)
                    break

                pose = self.get_robot_pose()
                if pose is None:
                    break
                distance = math.sqrt((pose[0] - start_x) ** 2 + (pose[1] - start_y) ** 2)
                if distance >= target_distance:
                    break
                self.cmd_vel_pub.publish(cmd)
                rate.sleep()
        else:
            duration = target_distance / max(abs(cmd.linear.x), 0.05)
            end_time = rospy.Time.now() + rospy.Duration(duration)
            rate = rospy.Rate(15)
            while not rospy.is_shutdown() and rospy.Time.now() < end_time:
                scan_age = self.get_scan_age()
                rear_clearance = self.sector_clearance(math.radians(140), math.radians(-140))
                if scan_age is not None and scan_age <= self.scan_stale_timeout and rear_clearance is not None and rear_clearance < self.recovery_clearance:
                    rospy.logwarn("Stopping timed recovery backup early -- rear clearance only %.2fm", rear_clearance)
                    break
                self.cmd_vel_pub.publish(cmd)
                rate.sleep()

        self.stop_robot()

    def perform_escape_recovery(self):
        rospy.logwarn("Running escape recovery: cancel goal, rotate toward open side, then back up")
        self.move_base_client.cancel_goal()
        self.stop_robot()
        rospy.sleep(0.5)

        if self.get_scan_age() is None or self.get_scan_age() > self.scan_stale_timeout:
            rospy.logwarn("Laser scan is stale during recovery; using timed turn")

        turn_direction = self.choose_turn_direction()
        self.rotate_for_recovery(turn_direction)
        self.backup_for_recovery()
        rospy.sleep(1.0)

    def send_move_base_goal(self, x, y):
        """Send a goal to move_base and wait for result. Returns True on success."""
        if not self.wait_for_fresh_pose(2.0):
            rospy.logwarn("Robot pose is stale before goal dispatch; refusing to send goal until TF recovers")
            return False

        goal = MoveBaseGoal()
        goal.target_pose.header.frame_id = "odom"
        goal.target_pose.header.stamp = rospy.Time.now()
        goal.target_pose.pose.position.x = x
        goal.target_pose.pose.position.y = y
        goal.target_pose.pose.position.z = 0.0
        goal.target_pose.pose.orientation.w = 1.0

        self.move_base_client.send_goal(goal)
        finished = self.move_base_client.wait_for_result(rospy.Duration(self.waypoint_timeout))

        if not finished:
            self.move_base_client.cancel_goal()
            rospy.logwarn("move_base timed out reaching (%.2f, %.2f)", x, y)
            return False

        state = self.move_base_client.get_state()
        if state == actionlib.GoalStatus.SUCCEEDED:
            return True
        else:
            rospy.logwarn("move_base failed for (%.2f, %.2f) -- state %d", x, y, state)
            return False

    def clear_costmaps(self):
        """Ask move_base to clear costmaps -- helps recover from stuck states."""
        try:
            from std_srvs.srv import Empty
            rospy.wait_for_service('/move_base/clear_costmaps', timeout=2.0)
            clear = rospy.ServiceProxy('/move_base/clear_costmaps', Empty)
            clear()
            rospy.loginfo("Costmaps cleared")
        except Exception:
            rospy.logwarn("Could not clear costmaps")

    def publish_progress(self):
        """Publish current progress"""
        total = len(self.waypoints)
        msg = "{}/{} waypoints ({}%)".format(
            self.current_index, total,
            int(100.0 * self.current_index / total) if total > 0 else 0
        )
        self.progress_pub.publish(String(data=msg))

    def run(self):
        # Wait for subscribers to connect and costmap to populate
        rospy.loginfo("Waiting 5s for costmap to populate from lidar...")
        rospy.sleep(5.0)

        rospy.loginfo("Starting coverage mission!")

        while self.current_index < len(self.waypoints) and not rospy.is_shutdown():
            x, y = self.waypoints[self.current_index]
            waypoint_failures = 0

            if not self.waypoint_is_valid(x, y):
                rospy.logwarn("Skipping waypoint %d/%d because the target is invalid in the live environment",
                              self.current_index + 1, len(self.waypoints))
                self.current_index += 1
                continue

            while waypoint_failures < self.max_waypoint_failures and not rospy.is_shutdown():
                rospy.loginfo("Waypoint %d/%d attempt %d/%d: (%.2f, %.2f)",
                              self.current_index + 1, len(self.waypoints),
                              waypoint_failures + 1, self.max_waypoint_failures, x, y)
                self.publish_progress()

                if not self.waypoint_is_valid(x, y):
                    waypoint_failures = self.max_waypoint_failures
                    break

                success = self.send_move_base_goal(x, y)
                if success:
                    rospy.loginfo("Reached waypoint %d/%d",
                                  self.current_index + 1, len(self.waypoints))

                    # Only capture data at successfully reached waypoints
                    rospy.loginfo("Dwelling for %.1f s (thermal capture)", self.dwell_time)
                    self.capture_ready_pub.publish(Bool(data=True))
                    rospy.sleep(self.dwell_time)
                    self.capture_ready_pub.publish(Bool(data=False))
                    break

                waypoint_failures += 1
                rospy.logwarn("Failed waypoint %d/%d on attempt %d/%d",
                              self.current_index + 1, len(self.waypoints),
                              waypoint_failures, self.max_waypoint_failures)

                if waypoint_failures < self.max_waypoint_failures:
                    self.perform_escape_recovery()

            if waypoint_failures >= self.max_waypoint_failures:
                rospy.logwarn("Skipping waypoint %d/%d after %d failed attempts",
                              self.current_index + 1, len(self.waypoints),
                              self.max_waypoint_failures)

            self.current_index += 1

        # Mission complete
        rospy.loginfo("Coverage mission complete! %d/%d waypoints visited",
                      self.current_index, len(self.waypoints))
        self.complete_pub.publish(Bool(data=True))
        self.publish_progress()

        rospy.spin()


if __name__ == '__main__':
    try:
        planner = CoveragePlanner()
        planner.run()
    except rospy.ROSInterruptException:
        pass
