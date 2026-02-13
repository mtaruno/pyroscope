#!/usr/bin/env python

"""
Lidar Obstacle Detector
Subscribes to /scan and publishes /obstacle_detected (Bool) and /obstacle_min_distance (Float32)
based on whether any reading in the front arc is below the stop distance.
"""

import rospy
import math
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Bool, Float32


class LidarObstacleDetector:
    def __init__(self):
        rospy.init_node('lidar_obstacle_detector', anonymous=False)

        # Parameters
        self.stop_distance = rospy.get_param('~stop_distance', 0.30)
        self.front_arc_degrees = rospy.get_param('~front_arc_degrees', 30.0)
        self.min_range = rospy.get_param('~min_range', 0.12)  # RPLidar minimum reliable range

        # Publishers
        self.obstacle_pub = rospy.Publisher('/obstacle_detected', Bool, queue_size=1)
        self.distance_pub = rospy.Publisher('/obstacle_min_distance', Float32, queue_size=1)

        # Subscriber
        rospy.Subscriber('/scan', LaserScan, self.scan_callback)

        rospy.loginfo("Lidar Obstacle Detector started")
        rospy.loginfo("  stop_distance: %.2f m", self.stop_distance)
        rospy.loginfo("  front_arc: +/- %.0f degrees", self.front_arc_degrees)
        rospy.loginfo("  min_range: %.2f m", self.min_range)

    def scan_callback(self, scan):
        front_arc_rad = math.radians(self.front_arc_degrees)

        min_distance = float('inf')

        for i, r in enumerate(scan.ranges):
            # Skip invalid readings
            if r < self.min_range or r > scan.range_max or math.isnan(r) or math.isinf(r):
                continue

            # Calculate angle for this reading
            angle = scan.angle_min + i * scan.angle_increment

            # Check if within front arc (around 0 degrees)
            if abs(angle) <= front_arc_rad:
                if r < min_distance:
                    min_distance = r

        obstacle = min_distance < self.stop_distance

        self.obstacle_pub.publish(Bool(data=obstacle))
        self.distance_pub.publish(Float32(data=min_distance))

        if obstacle:
            rospy.logwarn_throttle(1.0, "Obstacle at %.2f m!", min_distance)


if __name__ == '__main__':
    try:
        detector = LidarObstacleDetector()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
