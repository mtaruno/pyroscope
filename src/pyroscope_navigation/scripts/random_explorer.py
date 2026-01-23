#!/usr/bin/env python

"""
Random Exploration Node for Pyroscope
Simple random walk exploration - no odometry needed!
Robot randomly moves forward, then turns, exploring the environment
"""

import rospy
from geometry_msgs.msg import Twist
import random
import math


class RandomExplorer:
    def __init__(self):
        rospy.init_node('random_explorer', anonymous=False)

        # Parameters
        self.forward_duration = rospy.get_param('~forward_duration', 3.0)  # seconds
        self.turn_duration = rospy.get_param('~turn_duration', 2.0)  # seconds
        self.forward_speed = rospy.get_param('~forward_speed', 0.2)  # m/s
        self.turn_speed = rospy.get_param('~turn_speed', 0.5)  # rad/s
        self.update_rate = rospy.get_param('~update_rate', 10.0)  # Hz

        # State
        self.current_state = "forward"  # "forward" or "turning"
        self.state_start_time = rospy.Time.now()
        self.current_duration = self.forward_duration

        # Publisher
        self.cmd_vel_pub = rospy.Publisher('/cmd_vel', Twist, queue_size=1)

        # Timer for control loop
        self.rate = rospy.Rate(self.update_rate)

        rospy.loginfo("Random Explorer initialized")
        rospy.loginfo("  Forward speed: {} m/s for ~{} seconds".format(
            self.forward_speed, self.forward_duration))
        rospy.loginfo("  Turn speed: {} rad/s for ~{} seconds".format(
            self.turn_speed, self.turn_duration))
        rospy.loginfo("Starting exploration!")

    def generate_random_forward_duration(self):
        """Generate random forward duration with some variation"""
        variation = self.forward_duration * 0.3  # +/- 30%
        return self.forward_duration + random.uniform(-variation, variation)

    def generate_random_turn_duration(self):
        """Generate random turn duration with some variation"""
        variation = self.turn_duration * 0.3  # +/- 30%
        return self.turn_duration + random.uniform(-variation, variation)

    def generate_random_turn_direction(self):
        """Randomly choose left or right turn"""
        return random.choice([-1, 1])

    def transition_to_forward(self):
        """Transition to forward movement state"""
        self.current_state = "forward"
        self.current_duration = self.generate_random_forward_duration()
        self.state_start_time = rospy.Time.now()
        rospy.loginfo("Moving forward for {:.1f} seconds".format(self.current_duration))

    def transition_to_turning(self):
        """Transition to turning state"""
        self.current_state = "turning"
        self.current_duration = self.generate_random_turn_duration()
        self.turn_direction = self.generate_random_turn_direction()
        self.state_start_time = rospy.Time.now()

        direction = "left" if self.turn_direction > 0 else "right"
        rospy.loginfo("Turning {} for {:.1f} seconds".format(direction, self.current_duration))

    def run(self):
        """Main exploration loop"""

        while not rospy.is_shutdown():
            # Check if it's time to switch states
            elapsed = (rospy.Time.now() - self.state_start_time).to_sec()

            if elapsed >= self.current_duration:
                # Switch states
                if self.current_state == "forward":
                    self.transition_to_turning()
                else:
                    self.transition_to_forward()

            # Generate velocity command based on current state
            cmd = Twist()

            if self.current_state == "forward":
                cmd.linear.x = self.forward_speed
                cmd.angular.z = 0.0
            else:  # turning
                cmd.linear.x = 0.0
                cmd.angular.z = self.turn_speed * self.turn_direction

            # Publish command
            self.cmd_vel_pub.publish(cmd)

            # Sleep to maintain rate
            self.rate.sleep()

        # Stop robot when shutting down
        self.cmd_vel_pub.publish(Twist())
        rospy.loginfo("Random explorer stopped")


if __name__ == '__main__':
    try:
        explorer = RandomExplorer()
        explorer.run()
    except rospy.ROSInterruptException:
        pass
