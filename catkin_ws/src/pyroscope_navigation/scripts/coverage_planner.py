#!/usr/bin/env python

"""
Coverage Path Planner for Pyroscope
Generates a boustrophedon (lawnmower) pattern over a rectangular area
and sends waypoints sequentially to the waypoint controller.
Pauses at each waypoint for thermal camera capture.
"""

import rospy
import math
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import Bool, String


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
        self.waypoint_timeout = rospy.get_param('~waypoint_timeout', 30.0)

        # State
        self.goal_reached = False
        self.obstacle_detected = False
        self.waypoints = []
        self.current_index = 0

        # Publishers
        self.waypoint_pub = rospy.Publisher('/nav/target_waypoint', PoseStamped, queue_size=1)
        self.capture_ready_pub = rospy.Publisher('/coverage/capture_ready', Bool, queue_size=1)
        self.progress_pub = rospy.Publisher('/coverage/progress', String, queue_size=1)
        self.complete_pub = rospy.Publisher('/coverage/complete', Bool, queue_size=1)

        # Subscribers
        rospy.Subscriber('/nav/goal_reached', Bool, self.goal_reached_callback)
        rospy.Subscriber('/obstacle_detected', Bool, self.obstacle_callback)

        # Generate waypoints
        self.generate_waypoints()

        rospy.loginfo("Coverage Planner initialized")
        rospy.loginfo("  Area: %.1f x %.1f m", self.area_width, self.area_height)
        rospy.loginfo("  Row spacing: %.1f m, Waypoint spacing: %.1f m", self.row_spacing, self.waypoint_spacing)
        rospy.loginfo("  Origin: (%.1f, %.1f)", self.origin_x, self.origin_y)
        rospy.loginfo("  Total waypoints: %d", len(self.waypoints))
        rospy.loginfo("  Dwell time: %.1f s", self.dwell_time)

    def goal_reached_callback(self, msg):
        if msg.data:
            self.goal_reached = True

    def obstacle_callback(self, msg):
        self.obstacle_detected = msg.data

    def generate_waypoints(self):
        """Generate boustrophedon (lawnmower) waypoints"""
        self.waypoints = []

        num_rows = int(math.ceil(self.area_height / self.row_spacing)) + 1
        num_cols = int(math.ceil(self.area_width / self.waypoint_spacing)) + 1

        for row in range(num_rows):
            y = self.origin_y + row * self.row_spacing
            # Cap at area boundary
            if y > self.origin_y + self.area_height:
                y = self.origin_y + self.area_height

            # Alternate direction for lawnmower pattern
            if row % 2 == 0:
                # Left to right
                col_range = range(num_cols)
            else:
                # Right to left
                col_range = range(num_cols - 1, -1, -1)

            for col in col_range:
                x = self.origin_x + col * self.waypoint_spacing
                # Cap at area boundary
                if x > self.origin_x + self.area_width:
                    x = self.origin_x + self.area_width

                self.waypoints.append((x, y))

        rospy.loginfo("Generated %d waypoints in %d rows", len(self.waypoints), num_rows)

    def send_waypoint(self, x, y):
        """Publish a waypoint to the waypoint controller"""
        msg = PoseStamped()
        msg.header.stamp = rospy.Time.now()
        msg.header.frame_id = "odom"
        msg.pose.position.x = x
        msg.pose.position.y = y
        msg.pose.position.z = 0.0
        msg.pose.orientation.w = 1.0
        self.waypoint_pub.publish(msg)

    def publish_progress(self):
        """Publish current progress"""
        total = len(self.waypoints)
        msg = "{}/{} waypoints ({}%)".format(
            self.current_index, total,
            int(100.0 * self.current_index / total) if total > 0 else 0
        )
        self.progress_pub.publish(String(data=msg))

    def run(self):
        rate = rospy.Rate(10)

        # Wait for subscribers to connect
        rospy.sleep(2.0)

        rospy.loginfo("Starting coverage mission!")

        while self.current_index < len(self.waypoints) and not rospy.is_shutdown():
            x, y = self.waypoints[self.current_index]

            # Send waypoint
            self.goal_reached = False
            self.send_waypoint(x, y)
            rospy.loginfo("Waypoint %d/%d: (%.2f, %.2f)",
                          self.current_index + 1, len(self.waypoints), x, y)
            self.publish_progress()

            # Wait for goal reached or timeout
            start_time = rospy.Time.now()
            obstacle_start = None

            while not rospy.is_shutdown():
                elapsed = (rospy.Time.now() - start_time).to_sec()

                # Goal reached
                if self.goal_reached:
                    rospy.loginfo("Reached waypoint %d/%d", self.current_index + 1, len(self.waypoints))
                    break

                # Timeout
                if elapsed > self.waypoint_timeout:
                    rospy.logwarn("Timeout reaching waypoint %d, skipping", self.current_index + 1)
                    break

                # Obstacle detected — wait 5s then skip
                if self.obstacle_detected:
                    if obstacle_start is None:
                        obstacle_start = rospy.Time.now()
                        rospy.logwarn("Obstacle detected while heading to waypoint %d", self.current_index + 1)
                    elif (rospy.Time.now() - obstacle_start).to_sec() > 5.0:
                        rospy.logwarn("Obstacle persists, skipping waypoint %d", self.current_index + 1)
                        break
                else:
                    obstacle_start = None

                rate.sleep()

            # Dwell at waypoint for thermal capture
            rospy.loginfo("Dwelling for %.1f s (thermal capture)", self.dwell_time)
            self.capture_ready_pub.publish(Bool(data=True))
            rospy.sleep(self.dwell_time)
            self.capture_ready_pub.publish(Bool(data=False))

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
