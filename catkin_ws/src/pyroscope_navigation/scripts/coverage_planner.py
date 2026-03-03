#!/usr/bin/env python

"""
Coverage Path Planner for Pyroscope
Generates a boustrophedon (lawnmower) pattern over a rectangular area
and sends waypoints to move_base for execution with obstacle avoidance.
Pauses at each waypoint for thermal camera capture.
"""

import rospy
import math
import actionlib
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from std_msgs.msg import Bool, String


# Margin inset from area boundary so waypoints never land on walls.
# Must be >= robot half-width (0.125m) + inflation_radius (0.15m).
WALL_MARGIN = 0.20  # meters


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

        # Max consecutive failures before aborting mission
        self.max_consecutive_failures = 3

        # State
        self.waypoints = []
        self.current_index = 0

        # Publishers
        self.capture_ready_pub = rospy.Publisher('/coverage/capture_ready', Bool, queue_size=1)
        self.progress_pub = rospy.Publisher('/coverage/progress', String, queue_size=1)
        self.complete_pub = rospy.Publisher('/coverage/complete', Bool, queue_size=1)

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

    def generate_waypoints(self):
        """Generate boustrophedon (lawnmower) waypoints with wall margin inset."""
        self.waypoints = []

        # Inset the scannable area so waypoints never touch walls
        min_x = self.origin_x + WALL_MARGIN
        max_x = self.origin_x + self.area_width - WALL_MARGIN
        min_y = self.origin_y + WALL_MARGIN
        max_y = self.origin_y + self.area_height - WALL_MARGIN

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

    def send_move_base_goal(self, x, y):
        """Send a goal to move_base and wait for result. Returns True on success."""
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

        consecutive_failures = 0

        while self.current_index < len(self.waypoints) and not rospy.is_shutdown():
            x, y = self.waypoints[self.current_index]

            rospy.loginfo("Waypoint %d/%d: (%.2f, %.2f)",
                          self.current_index + 1, len(self.waypoints), x, y)
            self.publish_progress()

            success = self.send_move_base_goal(x, y)
            if success:
                rospy.loginfo("Reached waypoint %d/%d",
                              self.current_index + 1, len(self.waypoints))
                consecutive_failures = 0

                # Only capture data at successfully reached waypoints
                rospy.loginfo("Dwelling for %.1f s (thermal capture)", self.dwell_time)
                self.capture_ready_pub.publish(Bool(data=True))
                rospy.sleep(self.dwell_time)
                self.capture_ready_pub.publish(Bool(data=False))
            else:
                consecutive_failures += 1
                rospy.logwarn("Failed waypoint %d/%d (%d consecutive failures)",
                              self.current_index + 1, len(self.waypoints),
                              consecutive_failures)

                if consecutive_failures >= self.max_consecutive_failures:
                    rospy.logwarn("Too many consecutive failures -- clearing costmaps and skipping waypoint")
                    self.clear_costmaps()
                    rospy.sleep(2.0)
                    consecutive_failures = 0

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
