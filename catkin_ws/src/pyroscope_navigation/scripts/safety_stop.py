#!/usr/bin/env python

"""
Safety Stop Node
Last-resort safety layer that overrides /cmd_vel with a stop command
when an obstacle is detected. Works during any mode (teleop, move_base, exploration).
"""

import rospy
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool


class SafetyStop:
    def __init__(self):
        rospy.init_node('safety_stop', anonymous=False)

        # Parameters
        self.override_duration = rospy.get_param('~override_duration', 0.5)
        self.rate_hz = rospy.get_param('~rate', 20.0)

        # State
        self.obstacle_detected = False
        self.last_obstacle_time = rospy.Time(0)

        # Publisher
        self.cmd_vel_pub = rospy.Publisher('/cmd_vel', Twist, queue_size=1)

        # Subscriber
        rospy.Subscriber('/obstacle_detected', Bool, self.obstacle_callback)

        self.rate = rospy.Rate(self.rate_hz)

        rospy.loginfo("Safety Stop started")
        rospy.loginfo("  override_duration: %.2f s", self.override_duration)

    def obstacle_callback(self, msg):
        if msg.data:
            self.obstacle_detected = True
            self.last_obstacle_time = rospy.Time.now()
        else:
            # Only clear if enough time has passed since last detection
            elapsed = (rospy.Time.now() - self.last_obstacle_time).to_sec()
            if elapsed > self.override_duration:
                self.obstacle_detected = False

    def run(self):
        while not rospy.is_shutdown():
            if self.obstacle_detected:
                self.cmd_vel_pub.publish(Twist())  # zero velocity
            self.rate.sleep()


if __name__ == '__main__':
    try:
        stopper = SafetyStop()
        stopper.run()
    except rospy.ROSInterruptException:
        pass
