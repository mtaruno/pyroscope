#!/usr/bin/env python

"""
Fake Odometry Publisher for Testing
Publishes static odometry at origin - useful for testing controller logic
WARNING: Robot won't actually navigate properly with this, just for testing cmd_vel output
"""

import rospy
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Quaternion


def publish_fake_odom():
    rospy.init_node('fake_odom_publisher', anonymous=False)

    pub = rospy.Publisher('/odom', Odometry, queue_size=10)
    rate = rospy.Rate(20)  # 20 Hz

    rospy.loginfo("Publishing fake odometry at origin (0, 0)")
    rospy.logwarn("This is FAKE odometry for testing only!")

    while not rospy.is_shutdown():
        odom = Odometry()
        odom.header.stamp = rospy.Time.now()
        odom.header.frame_id = "odom"
        odom.child_frame_id = "base_link"

        # Position at origin
        odom.pose.pose.position.x = 0.0
        odom.pose.pose.position.y = 0.0
        odom.pose.pose.position.z = 0.0

        # Orientation (facing forward)
        odom.pose.pose.orientation.x = 0.0
        odom.pose.pose.orientation.y = 0.0
        odom.pose.pose.orientation.z = 0.0
        odom.pose.pose.orientation.w = 1.0

        pub.publish(odom)
        rate.sleep()


if __name__ == '__main__':
    try:
        publish_fake_odom()
    except rospy.ROSInterruptException:
        pass
