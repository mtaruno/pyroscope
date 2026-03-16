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
from geometry_msgs.msg import Twist, Point
from nav_msgs.msg import OccupancyGrid
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Bool, String, ColorRGBA
from visualization_msgs.msg import Marker, MarkerArray


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
        self.pose_stale_timeout = rospy.get_param('~pose_stale_timeout', 2.0)
        self.scan_stale_timeout = rospy.get_param('~scan_stale_timeout', 1.0)
        self.costmap_stale_timeout = rospy.get_param('~costmap_stale_timeout', 2.0)

        # Goal tolerance for proximity-based capture (should match dwa_planner.yaml xy_goal_tolerance)
        self.xy_goal_tolerance = rospy.get_param('~xy_goal_tolerance', 0.5)

        # Recovery parameters
        self.recovery_turn_speed = rospy.get_param('~recovery_turn_speed', 0.7)
        self.recovery_turn_angle = rospy.get_param('~recovery_turn_angle', 1.0)
        self.recovery_backup_speed = rospy.get_param('~recovery_backup_speed', -0.12)
        self.recovery_backup_distance = rospy.get_param('~recovery_backup_distance', 0.35)
        self.recovery_clearance = rospy.get_param('~recovery_clearance', 0.30)
        self.waypoint_validation_radius = rospy.get_param('~waypoint_validation_radius', 0.18)
        self.waypoint_cost_threshold = int(rospy.get_param('~waypoint_cost_threshold', 200))
        self.scan_blocked_margin = rospy.get_param('~scan_blocked_margin', 2.0)
        self.scan_blocked_sector = rospy.get_param('~scan_blocked_sector', 0.20)

        # State
        self.waypoints = []
        self.current_index = 0
        self.latest_scan = None
        self.latest_scan_stamp = None
        self.latest_costmap = None
        self.latest_costmap_stamp = None
        self.latest_map = None  # raw SLAM /map (0=free, 100=occupied, -1=unknown)
        self.goal_frame = "map"  # SLAM map frame for goals and markers
        self.visited_positions = []  # list of (x, y) where we already captured
        self.mission_start_x = 0.0
        self.mission_start_y = 0.0
        # Publishers
        self.cmd_vel_pub = rospy.Publisher('/cmd_vel', Twist, queue_size=1)
        self.capture_ready_pub = rospy.Publisher('/coverage/capture_ready', Bool, queue_size=1)
        self.progress_pub = rospy.Publisher('/coverage/progress', String, queue_size=1)
        self.complete_pub = rospy.Publisher('/coverage/complete', Bool, queue_size=1)
        self.waypoint_markers_pub = rospy.Publisher('/coverage/waypoint_markers', MarkerArray, queue_size=1, latch=True)
        self.scan_sub = rospy.Subscriber('/scan', LaserScan, self.scan_callback, queue_size=1)
        self.costmap_sub = rospy.Subscriber('/move_base/global_costmap/costmap', OccupancyGrid, self.costmap_callback, queue_size=1)
        self.map_sub = rospy.Subscriber('/map', OccupancyGrid, self.map_callback, queue_size=1)
        self.tf_listener = tf.TransformListener()

        # move_base action client
        self.move_base_client = actionlib.SimpleActionClient('move_base', MoveBaseAction)
        rospy.loginfo("Waiting for move_base action server...")
        if not self.move_base_client.wait_for_server(rospy.Duration(30.0)):
            rospy.logfatal("move_base action server not available -- aborting")
            rospy.signal_shutdown("move_base unavailable")
            return

        rospy.loginfo("Connected to move_base action server")
        rospy.loginfo("Coverage Planner ready")
        rospy.loginfo("  Area: %.1f x %.1f m, spacing: %.1fm, row: %.1fm, margin: %.2fm",
                      self.area_width, self.area_height, self.waypoint_spacing,
                      self.row_spacing, WALL_MARGIN)
        rospy.loginfo("  Dwell: %.1fs, timeout: %.1fs, retries: %d, proximity: %.2fm",
                      self.dwell_time, self.waypoint_timeout,
                      self.max_waypoint_failures, self.xy_goal_tolerance)
        rospy.loginfo("  Waypoints will be generated from SLAM map once ready")

    def find_next_free_waypoint(self):
        """Find the nearest unvisited free cell in the SLAM map, at least
        row_spacing away from all previously visited waypoints.
        Constrained to within area_width x area_height of the mission start.
        Returns (x, y) or None if no suitable cell found."""
        m = self.latest_map
        if m is None:
            return None

        pose = self.get_robot_pose()
        if pose is None:
            return None
        robot_x, robot_y = pose[0], pose[1]

        info = m.info
        res = info.resolution
        ox = info.origin.position.x
        oy = info.origin.position.y
        spacing = self.row_spacing
        spacing_sq = spacing * spacing

        # Search area bounds (centred on mission start position)
        half_w = self.area_width / 2.0
        half_h = self.area_height / 2.0
        start_x = self.mission_start_x
        start_y = self.mission_start_y

        # Step through map at half the spacing (fine enough to not miss free patches)
        step = max(1, int(self.waypoint_spacing / res / 2))

        best = None
        best_dist = float('inf')

        for my in range(0, info.height, step):
            for mx in range(0, info.width, step):
                val = m.data[my * info.width + mx]
                if val != 0:
                    continue  # skip occupied/unknown

                wx = ox + (mx + 0.5) * res
                wy = oy + (my + 0.5) * res

                # Must be within the mission area
                if abs(wx - start_x) > half_w or abs(wy - start_y) > half_h:
                    continue

                # Quick distance check before expensive visited/obstacle checks
                dist = (wx - robot_x) ** 2 + (wy - robot_y) ** 2
                if dist >= best_dist:
                    continue

                # Must be at least spacing away from all visited waypoints
                too_close = False
                for vx, vy in self.visited_positions:
                    if (wx - vx) ** 2 + (wy - vy) ** 2 < spacing_sq:
                        too_close = True
                        break
                if too_close:
                    continue

                best_dist = dist
                best = (wx, wy)

        if best is not None:
            rospy.loginfo("Next free waypoint: (%.2f, %.2f) dist=%.2fm (step=%d, visited=%d)",
                          best[0], best[1], math.sqrt(best_dist), step,
                          len(self.visited_positions))
        else:
            # Count free cells in area to debug
            free_count = 0
            for cy in range(0, info.height, step):
                for cx in range(0, info.width, step):
                    if m.data[cy * info.width + cx] == 0:
                        cwx = ox + (cx + 0.5) * res
                        cwy = oy + (cy + 0.5) * res
                        if abs(cwx - start_x) <= half_w and abs(cwy - start_y) <= half_h:
                            free_count += 1
            rospy.logwarn("No free waypoint found: %d free cells in area, %d visited, "
                          "spacing=%.1f, area=%.0fx%.0f, start=(%.1f,%.1f)",
                          free_count, len(self.visited_positions), spacing,
                          self.area_width, self.area_height, start_x, start_y)
        return best

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

    def map_callback(self, msg):
        self.latest_map = msg

    def map_cell_value(self, x, y):
        """Return SLAM /map occupancy value at world (x,y): 0=free, 100=occupied, -1=unknown, None=OOB."""
        m = self.latest_map
        if m is None:
            return None
        info = m.info
        mx = int(math.floor((x - info.origin.position.x) / info.resolution))
        my = int(math.floor((y - info.origin.position.y) / info.resolution))
        if mx < 0 or my < 0 or mx >= info.width or my >= info.height:
            return None
        return m.data[my * info.width + mx]

    def stop_robot(self):
        self.cmd_vel_pub.publish(Twist())

    def get_robot_pose(self):
        # Prefer map frame (SLAM-corrected); fall back to odom if map not yet available
        for frame in ('map', 'odom'):
            try:
                common_time = self.tf_listener.getLatestCommonTime(frame, 'base_link')
                trans, rot = self.tf_listener.lookupTransform(frame, 'base_link', rospy.Time(0))
                yaw = tf.transformations.euler_from_quaternion(rot)[2]
                pose_age = abs((rospy.Time.now() - common_time).to_sec())
                return (trans[0], trans[1], yaw, pose_age)
            except (tf.Exception, tf.LookupException, tf.ConnectivityException, tf.ExtrapolationException):
                continue
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

    def snap_to_free_costmap(self, x, y, search_radius=0.6):
        """Snap waypoint to nearest low-cost cell in the live costmap.
        Uses costmap (not raw /map) so inflation and lidar updates are included.
        Only snaps if the original position is above the cost threshold."""
        if self.latest_costmap is None:
            return x, y

        center = self.world_to_costmap(x, y)
        if center is None:
            return x, y

        mx, my = center
        cost = self.costmap_cell(mx, my)

        # Already free enough -- no snap needed
        if cost is not None and 0 <= cost < self.waypoint_cost_threshold:
            return x, y

        res = self.latest_costmap.info.resolution
        steps = int(math.ceil(search_radius / res))
        best_x, best_y = None, None
        best_cost = self.waypoint_cost_threshold
        best_dist = float('inf')

        for dx in range(-steps, steps + 1):
            for dy in range(-steps, steps + 1):
                dist = math.sqrt(dx * dx + dy * dy) * res
                if dist > search_radius:
                    continue
                nx = mx + dx
                ny = my + dy
                c = self.costmap_cell(nx, ny)
                if c is None or c < 0:
                    continue
                # Prefer lowest cost, then closest distance
                if c < best_cost or (c == best_cost and dist < best_dist):
                    best_cost = c
                    best_dist = dist
                    ox = self.latest_costmap.info.origin.position.x
                    oy = self.latest_costmap.info.origin.position.y
                    best_x = ox + (nx + 0.5) * res
                    best_y = oy + (ny + 0.5) * res

        if best_x is not None:
            rospy.loginfo("Snapped waypoint (%.2f,%.2f)->(%.2f,%.2f) cost %d->%d dist %.2fm",
                          x, y, best_x, best_y, cost if cost is not None else -1,
                          best_cost, best_dist)
            return best_x, best_y

        rospy.logwarn("No free cell found within %.2fm of (%.2f,%.2f) -- skipping snap", search_radius, x, y)
        return x, y

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
        rospy.logwarn("Running escape recovery: cancel goal, back up straight")
        self.move_base_client.cancel_goal()
        self.stop_robot()
        rospy.sleep(0.5)
        self.backup_for_recovery()
        rospy.sleep(0.5)

    def send_move_base_goal(self, x, y):
        """Send a goal to move_base and wait for result.
        Returns True if move_base succeeds OR if the robot gets within
        xy_goal_tolerance of the target (proximity capture), whichever comes first.
        """
        pose = self.get_robot_pose()
        if pose is not None:
            rospy.loginfo("Robot pose before goal: (%.2f, %.2f) age=%.2fs target=(%.2f,%.2f) dist=%.2fm",
                          pose[0], pose[1], pose[3], x, y,
                          math.sqrt((pose[0]-x)**2 + (pose[1]-y)**2))
        if not self.wait_for_fresh_pose(2.0):
            rospy.logwarn("Robot pose is stale before goal dispatch; refusing to send goal until TF recovers")
            return False

        goal = MoveBaseGoal()
        goal.target_pose.header.frame_id = self.goal_frame
        goal.target_pose.header.stamp = rospy.Time.now()
        goal.target_pose.pose.position.x = x
        goal.target_pose.pose.position.y = y
        goal.target_pose.pose.position.z = 0.0
        goal.target_pose.pose.orientation.w = 1.0

        self.move_base_client.send_goal(goal)

        # Poll for move_base success OR proximity to target
        rate = rospy.Rate(10)
        deadline = rospy.Time.now() + rospy.Duration(self.waypoint_timeout)

        while not rospy.is_shutdown() and rospy.Time.now() < deadline:
            state = self.move_base_client.get_state()

            if state == actionlib.GoalStatus.SUCCEEDED:
                rospy.loginfo("move_base reported SUCCEEDED for (%.2f, %.2f)", x, y)
                return True

            if state in (actionlib.GoalStatus.ABORTED,
                         actionlib.GoalStatus.REJECTED,
                         actionlib.GoalStatus.PREEMPTED):
                # Even on abort, check proximity before giving up
                pose = self.get_robot_pose()
                if pose is not None:
                    dist = math.sqrt((pose[0] - x) ** 2 + (pose[1] - y) ** 2)
                    if dist <= self.xy_goal_tolerance:
                        rospy.loginfo("Proximity capture: robot %.2fm from (%.2f, %.2f) after state %d",
                                      dist, x, y, state)
                        self.move_base_client.cancel_goal()
                        return True
                rospy.logwarn("move_base failed for (%.2f, %.2f) -- state %d", x, y, state)
                return False

            # Proximity check while goal is still active
            pose = self.get_robot_pose()
            if pose is not None:
                dist = math.sqrt((pose[0] - x) ** 2 + (pose[1] - y) ** 2)
                if dist <= self.xy_goal_tolerance:
                    rospy.loginfo("Proximity capture: robot %.2fm from (%.2f, %.2f) -- cancelling goal",
                                  dist, x, y)
                    self.move_base_client.cancel_goal()
                    return True

            rate.sleep()

        # Timeout: final proximity check before failing
        pose = self.get_robot_pose()
        if pose is not None:
            dist = math.sqrt((pose[0] - x) ** 2 + (pose[1] - y) ** 2)
            if dist <= self.xy_goal_tolerance:
                rospy.loginfo("Proximity capture on timeout: robot %.2fm from (%.2f, %.2f)", dist, x, y)
                self.move_base_client.cancel_goal()
                return True

        self.move_base_client.cancel_goal()
        rospy.logwarn("move_base timed out reaching (%.2f, %.2f)", x, y)
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

    def publish_waypoint_markers(self):
        """Publish all waypoints as RViz markers: grey=pending, green=done, yellow=current target."""
        array = MarkerArray()
        for i, (x, y) in enumerate(self.waypoints):
            m = Marker()
            m.header.frame_id = self.goal_frame
            m.header.stamp = rospy.Time.now()
            m.ns = "coverage_waypoints"
            m.id = i
            m.type = Marker.CYLINDER
            m.action = Marker.ADD
            m.pose.position.x = x
            m.pose.position.y = y
            m.pose.position.z = 0.05
            m.pose.orientation.w = 1.0
            m.scale.x = 0.15
            m.scale.y = 0.15
            m.scale.z = 0.10
            if i < self.current_index:
                # Done -- green
                m.color = ColorRGBA(0.0, 0.9, 0.2, 0.8)
            elif i == self.current_index:
                # Current target -- yellow, larger
                m.color = ColorRGBA(1.0, 0.9, 0.0, 1.0)
                m.scale.x = 0.25
                m.scale.y = 0.25
                m.scale.z = 0.15
            else:
                # Pending -- grey
                m.color = ColorRGBA(0.6, 0.6, 0.6, 0.5)
            array.markers.append(m)
        self.waypoint_markers_pub.publish(array)

    def run(self):
        # Wait for SLAM map and costmap to initialize
        rospy.loginfo("Waiting for SLAM map and costmap to initialize...")
        deadline = rospy.Time.now() + rospy.Duration(30.0)
        rate = rospy.Rate(2)
        while not rospy.is_shutdown() and rospy.Time.now() < deadline:
            age = self.get_costmap_age()
            map_ready = self.latest_map is not None
            if age is not None and age < self.costmap_stale_timeout and map_ready:
                rospy.loginfo("SLAM map and costmap ready")
                break
            rate.sleep()
        else:
            rospy.logwarn("Map/costmap not fully ready after 30s -- proceeding anyway")

        # Record mission start position (centre of search area)
        pose = self.get_robot_pose()
        if pose is not None:
            self.mission_start_x = pose[0]
            self.mission_start_y = pose[1]
            rospy.loginfo("Mission start position: (%.2f, %.2f)", pose[0], pose[1])
        else:
            self.mission_start_x = self.origin_x
            self.mission_start_y = self.origin_y
            rospy.logwarn("Cannot get pose -- using origin (%.2f, %.2f) as start",
                          self.origin_x, self.origin_y)

        # Dynamic waypoint selection: pick nearest free white cell each time
        total_target = int(rospy.get_param('~total_waypoints', 0))
        if total_target <= 0:
            # Estimate from area and spacing
            ew = self.area_width - 2 * WALL_MARGIN
            eh = self.area_height - 2 * WALL_MARGIN
            if ew > 0 and eh > 0:
                total_target = max(1, int(math.ceil(ew / self.waypoint_spacing)) *
                                      int(math.ceil(eh / self.row_spacing)))
            else:
                total_target = 9

        rospy.loginfo("Starting dynamic coverage mission: target %d waypoints", total_target)
        waypoint_count = 0
        consecutive_failures = 0

        # If no SLAM map after initial wait, generate blind grid as fallback
        fallback_waypoints = []
        if self.latest_map is None:
            rospy.logwarn("No SLAM map -- generating blind grid fallback")
            sx, sy = self.mission_start_x, self.mission_start_y
            hw, hh = self.area_width / 2.0 - WALL_MARGIN, self.area_height / 2.0 - WALL_MARGIN
            if hw > 0 and hh > 0:
                num_rows = max(1, int(math.ceil(2 * hh / self.row_spacing)) + 1)
                num_cols = max(1, int(math.ceil(2 * hw / self.waypoint_spacing)) + 1)
                for row in range(num_rows):
                    y_val = sy - hh + row * self.row_spacing
                    cols = range(num_cols) if row % 2 == 0 else range(num_cols - 1, -1, -1)
                    for col in cols:
                        x_val = sx - hw + col * self.waypoint_spacing
                        fallback_waypoints.append((x_val, y_val))
                rospy.loginfo("Blind grid fallback: %d waypoints", len(fallback_waypoints))
                total_target = len(fallback_waypoints)
            fallback_index = 0

        while waypoint_count < total_target and not rospy.is_shutdown():
            # Try SLAM-based dynamic waypoint; fall back to blind grid
            target = self.find_next_free_waypoint()

            if target is None:
                if fallback_waypoints and fallback_index < len(fallback_waypoints):
                    target = fallback_waypoints[fallback_index]
                    fallback_index += 1
                    rospy.loginfo("Using fallback grid waypoint: (%.2f, %.2f)", target[0], target[1])
                elif self.latest_map is None:
                    rospy.logwarn("No SLAM map and no fallback -- waiting...")
                    rospy.sleep(2.0)
                    consecutive_failures += 1
                    if consecutive_failures > 15:
                        rospy.logwarn("No map after 30s of waiting -- aborting")
                        break
                    continue
                else:
                    rospy.logwarn("No more free cells found in map -- mission complete")
                    break

            consecutive_failures = 0
            x, y = target

            # Update waypoints list for marker visualization
            self.waypoints = list(self.visited_positions) + [(x, y)]
            self.current_index = len(self.visited_positions)
            self.publish_waypoint_markers()

            rospy.loginfo("Waypoint %d/%d: navigating to (%.2f, %.2f)",
                          waypoint_count + 1, total_target, x, y)
            self.publish_progress()

            attempt = 0
            reached = False
            while attempt < self.max_waypoint_failures and not rospy.is_shutdown():
                success = self.send_move_base_goal(x, y)
                if success:
                    reached = True
                    break
                attempt += 1
                rospy.logwarn("Failed attempt %d/%d for (%.2f, %.2f)",
                              attempt, self.max_waypoint_failures, x, y)
                if attempt < self.max_waypoint_failures:
                    self.perform_escape_recovery()

            if reached:
                rospy.loginfo("Reached waypoint %d -- dwelling %.1fs",
                              waypoint_count + 1, self.dwell_time)
                self.capture_ready_pub.publish(Bool(data=True))
                rospy.sleep(self.dwell_time)
                self.capture_ready_pub.publish(Bool(data=False))
                self.visited_positions.append((x, y))
                waypoint_count += 1
            else:
                rospy.logwarn("Skipping unreachable waypoint (%.2f, %.2f)", x, y)
                # Mark it as visited so we don't try it again
                self.visited_positions.append((x, y))

        # Mission complete
        self.waypoints = list(self.visited_positions)
        self.current_index = len(self.waypoints)
        rospy.loginfo("Coverage mission complete! %d waypoints captured", waypoint_count)
        self.complete_pub.publish(Bool(data=True))
        self.publish_progress()
        self.publish_waypoint_markers()

        rospy.spin()


if __name__ == '__main__':
    try:
        planner = CoveragePlanner()
        planner.run()
    except rospy.ROSInterruptException:
        pass
