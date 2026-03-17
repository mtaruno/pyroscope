#!/usr/bin/env python

"""
Minimal waypoint sequencer for demo fallback navigation.
Publishes four odom-frame waypoints one at a time to waypoint_controller.py.
"""

import rospy
from geometry_msgs.msg import PoseStamped, Twist
from std_msgs.msg import Bool, String


class DemoWaypointSequence:
    def __init__(self):
        rospy.init_node('demo_waypoint_sequence', anonymous=False)

        self.frame_id = rospy.get_param('~frame_id', 'odom')
        self.dwell_time = rospy.get_param('~dwell_time', 1.0)
        self.goal_timeout = rospy.get_param('~goal_timeout', 25.0)
        self.skip_on_stall = rospy.get_param('~skip_on_stall', True)
        self.settle_time = rospy.get_param('~settle_time', 0.5)
        self.capture_on_skip = rospy.get_param('~capture_on_skip', True)

        self.waypoints = [
            (rospy.get_param('~x1', 1.0), rospy.get_param('~y1', 0.0)),
            (rospy.get_param('~x2', 1.0), rospy.get_param('~y2', 1.0)),
            (rospy.get_param('~x3', 0.0), rospy.get_param('~y3', 1.0)),
            (rospy.get_param('~x4', 0.0), rospy.get_param('~y4', 0.0)),
        ]

        self.goal_reached = False
        self.progress_stalled = False

        self.target_pub = rospy.Publisher('/nav/target_waypoint', PoseStamped, queue_size=1)
        self.cmd_vel_pub = rospy.Publisher('/cmd_vel', Twist, queue_size=1)
        self.capture_ready_pub = rospy.Publisher('/coverage/capture_ready', Bool, queue_size=1)
        self.progress_pub = rospy.Publisher('/coverage/progress', String, queue_size=1)
        self.complete_pub = rospy.Publisher('/coverage/complete', Bool, queue_size=1)
        rospy.Subscriber('/nav/goal_reached', Bool, self.goal_reached_callback, queue_size=1)
        rospy.Subscriber('/nav/progress_stalled', Bool, self.progress_stalled_callback, queue_size=1)

        rospy.loginfo("Demo waypoint sequence initialized with %d waypoints", len(self.waypoints))
        for index, waypoint in enumerate(self.waypoints, start=1):
            rospy.loginfo("  %d: (%.2f, %.2f)", index, waypoint[0], waypoint[1])

    def goal_reached_callback(self, msg):
        self.goal_reached = bool(msg.data)

    def progress_stalled_callback(self, msg):
        self.progress_stalled = bool(msg.data)

    def publish_waypoint(self, x, y):
        msg = PoseStamped()
        msg.header.stamp = rospy.Time.now()
        msg.header.frame_id = self.frame_id
        msg.pose.position.x = x
        msg.pose.position.y = y
        msg.pose.position.z = 0.0
        msg.pose.orientation.w = 1.0
        self.goal_reached = False
        self.progress_stalled = False
        self.target_pub.publish(msg)
        rospy.loginfo("Sent waypoint: (%.2f, %.2f)", x, y)

    def publish_progress(self, done):
        total = len(self.waypoints)
        percent = int(round((float(done) / float(total)) * 100.0)) if total else 100
        msg = "{}/{} waypoints ({}%)".format(done, total, percent)
        self.progress_pub.publish(String(data=msg))

    def publish_status(self, text):
        self.progress_pub.publish(String(data=text))

    def publish_stop(self):
        self.cmd_vel_pub.publish(Twist())

    def publish_capture_ready_window(self):
        settle_end = rospy.Time.now() + rospy.Duration(self.settle_time)
        dwell_end = settle_end + rospy.Duration(self.dwell_time)
        rate = rospy.Rate(10)

        while not rospy.is_shutdown() and rospy.Time.now() < settle_end:
            self.publish_stop()
            self.capture_ready_pub.publish(Bool(data=False))
            rate.sleep()

        while not rospy.is_shutdown() and rospy.Time.now() < dwell_end:
            self.publish_stop()
            self.capture_ready_pub.publish(Bool(data=True))
            rate.sleep()

        self.publish_stop()
        self.capture_ready_pub.publish(Bool(data=False))

    def wait_for_result(self):
        deadline = rospy.Time.now() + rospy.Duration(self.goal_timeout)
        rate = rospy.Rate(10)

        while not rospy.is_shutdown():
            if self.goal_reached:
                return 'reached'

            if self.skip_on_stall and self.progress_stalled:
                return 'stalled'

            if rospy.Time.now() >= deadline:
                return 'timeout'

            rate.sleep()

        return 'shutdown'

    def run(self):
        rospy.sleep(1.0)
        self.complete_pub.publish(Bool(data=False))
        self.capture_ready_pub.publish(Bool(data=False))
        self.publish_progress(0)

        for index, (x, y) in enumerate(self.waypoints, start=1):
            if rospy.is_shutdown():
                return

            rospy.loginfo("Starting waypoint %d/%d", index, len(self.waypoints))
            self.publish_status("Navigating to waypoint {}/{}".format(index, len(self.waypoints)))
            self.publish_waypoint(x, y)
            result = self.wait_for_result()

            if result == 'reached':
                rospy.loginfo("Waypoint %d reached", index)
                self.publish_status(
                    "Dwelling at waypoint {}/{} for {:.1f}s".format(
                        index, len(self.waypoints), self.dwell_time
                    )
                )
                self.publish_capture_ready_window()
            elif result == 'stalled':
                rospy.logwarn("Waypoint %d stalled, skipping", index)
                self.publish_stop()
                if self.capture_on_skip:
                    self.publish_status(
                        "Waypoint {}/{} stalled; capturing at current stop".format(
                            index, len(self.waypoints)
                        )
                    )
                    self.publish_capture_ready_window()
            elif result == 'timeout':
                rospy.logwarn("Waypoint %d timed out after %.1f s, skipping", index, self.goal_timeout)
                self.publish_stop()
                if self.capture_on_skip:
                    self.publish_status(
                        "Waypoint {}/{} timed out; capturing at current stop".format(
                            index, len(self.waypoints)
                        )
                    )
                    self.publish_capture_ready_window()
            else:
                return

            self.publish_progress(index)

        rospy.loginfo("Demo waypoint sequence complete")
        self.publish_stop()
        self.complete_pub.publish(Bool(data=True))


if __name__ == '__main__':
    try:
        DemoWaypointSequence().run()
    except rospy.ROSInterruptException:
        pass
