#!/usr/bin/env python

"""
Test script to send a single waypoint to the controller
Useful for testing without running the full state machine
"""

import rospy
from geometry_msgs.msg import PoseStamped
import sys


def send_waypoint(x, y):
    rospy.init_node('test_waypoint_sender', anonymous=True)

    pub = rospy.Publisher('/nav/target_waypoint', PoseStamped, queue_size=1)
    rospy.sleep(1)  # Wait for publisher to register

    msg = PoseStamped()
    msg.header.stamp = rospy.Time.now()
    msg.header.frame_id = "odom"
    msg.pose.position.x = x
    msg.pose.position.y = y
    msg.pose.position.z = 0.0
    msg.pose.orientation.w = 1.0

    rospy.loginfo("Sending waypoint: ({}, {})".format(x, y))
    pub.publish(msg)
    rospy.sleep(1)  # Keep node alive briefly


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: rosrun pyroscope_navigation test_single_waypoint.py <x> <y>")
        print("Example: rosrun pyroscope_navigation test_single_waypoint.py 2.0 3.0")
        sys.exit(1)

    try:
        x = float(sys.argv[1])
        y = float(sys.argv[2])
        send_waypoint(x, y)
    except ValueError:
        print("Error: x and y must be numbers")
        sys.exit(1)
    except rospy.ROSInterruptException:
        pass
