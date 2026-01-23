#!/usr/bin/env python

"""
Random Exploration with Obstacle Detection Hook
Explores randomly but will stop/turn when obstacles detected (when you add the sensor)
"""

import rospy
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool
import random


class RandomExplorerWithObstacle:
    def __init__(self):
        rospy.init_node('random_explorer_obstacle', anonymous=False)

        # Parameters
        self.forward_duration = rospy.get_param('~forward_duration', 3.0)
        self.turn_duration = rospy.get_param('~turn_duration', 2.0)
        self.forward_speed = rospy.get_param('~forward_speed', 0.2)
        self.turn_speed = rospy.get_param('~turn_speed', 0.5)
        self.update_rate = rospy.get_param('~update_rate', 10.0)

        # State
        self.current_state = "forward"
        self.state_start_time = rospy.Time.now()
        self.current_duration = self.forward_duration
        self.obstacle_detected = False

        # Publisher
        self.cmd_vel_pub = rospy.Publisher('/cmd_vel', Twist, queue_size=1)

        # Subscriber for obstacle detection (future)
        # When you add ZED depth processing, publish True when obstacle ahead
        rospy.Subscriber('/obstacle_detected', Bool, self.obstacle_callback)

        self.rate = rospy.Rate(self.update_rate)

        rospy.loginfo("Random Explorer with Obstacle Detection initialized")
        rospy.loginfo("  Waiting for /obstacle_detected topic (optional)")
        rospy.loginfo("Starting exploration!")

    def obstacle_callback(self, msg):
        """Called when obstacle detection publishes (future feature)"""
        self.obstacle_detected = msg.data
        if msg.data:
            rospy.logwarn("Obstacle detected! Taking evasive action")
            # Force transition to turning to avoid obstacle
            self.transition_to_turning()

    def generate_random_forward_duration(self):
        variation = self.forward_duration * 0.3
        return self.forward_duration + random.uniform(-variation, variation)

    def generate_random_turn_duration(self):
        variation = self.turn_duration * 0.3
        return self.turn_duration + random.uniform(-variation, variation)

    def generate_random_turn_direction(self):
        return random.choice([-1, 1])

    def transition_to_forward(self):
        self.current_state = "forward"
        self.current_duration = self.generate_random_forward_duration()
        self.state_start_time = rospy.Time.now()
        self.obstacle_detected = False
        rospy.loginfo("Moving forward for {:.1f} seconds".format(self.current_duration))

    def transition_to_turning(self):
        self.current_state = "turning"
        self.current_duration = self.generate_random_turn_duration()
        self.turn_direction = self.generate_random_turn_direction()
        self.state_start_time = rospy.Time.now()
        direction = "left" if self.turn_direction > 0 else "right"
        rospy.loginfo("Turning {} for {:.1f} seconds".format(direction, self.current_duration))

    def run(self):
        while not rospy.is_shutdown():
            elapsed = (rospy.Time.now() - self.state_start_time).to_sec()

            # Check for state transition
            if elapsed >= self.current_duration:
                if self.current_state == "forward":
                    self.transition_to_turning()
                else:
                    self.transition_to_forward()

            # Generate velocity command
            cmd = Twist()

            if self.current_state == "forward" and not self.obstacle_detected:
                cmd.linear.x = self.forward_speed
                cmd.angular.z = 0.0
            elif self.current_state == "forward" and self.obstacle_detected:
                # Obstacle ahead while moving forward - stop and turn
                cmd.linear.x = 0.0
                cmd.angular.z = self.turn_speed * random.choice([-1, 1])
            else:  # turning
                cmd.linear.x = 0.0
                cmd.angular.z = self.turn_speed * self.turn_direction

            self.cmd_vel_pub.publish(cmd)
            self.rate.sleep()

        # Stop on shutdown
        self.cmd_vel_pub.publish(Twist())
        rospy.loginfo("Explorer stopped")


if __name__ == '__main__':
    try:
        explorer = RandomExplorerWithObstacle()
        explorer.run()
    except rospy.ROSInterruptException:
        pass
