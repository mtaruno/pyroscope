#!/usr/bin/env python

"""
Waypoint Controller Node for Pyroscope Navigation
Simple proportional controller that drives the robot to target waypoints
Publishes to /cmd_vel and monitors progress
"""

import rospy
from geometry_msgs.msg import Twist, PoseStamped
from nav_msgs.msg import Odometry
from std_msgs.msg import Bool
import math
import tf


class WaypointController:
    def __init__(self):
        rospy.init_node('waypoint_controller', anonymous=False)

        # Controller parameters
        self.linear_gain = rospy.get_param('~linear_gain', 0.5)
        self.angular_gain = rospy.get_param('~angular_gain', 1.5)
        self.max_linear_vel = rospy.get_param('~max_linear_vel', 0.12)  # m/s
        self.max_angular_vel = rospy.get_param('~max_angular_vel', 0.35)  # rad/s
        self.goal_tolerance = rospy.get_param('~goal_tolerance', 0.25)  # meters
        self.control_frequency = rospy.get_param('~control_frequency', 10.0)  # Hz
        self.heading_threshold = rospy.get_param('~heading_threshold', 0.35)  # rad
        self.turn_in_place_linear_vel = rospy.get_param('~turn_in_place_linear_vel', 0.0)
        self.progress_epsilon = rospy.get_param('~progress_epsilon', 0.03)  # meters
        self.stall_timeout = rospy.get_param('~stall_timeout', 4.0)  # seconds

        # State variables
        self.current_pose = None
        self.target_waypoint = None
        self.goal_reached = False
        self.last_progress_time = rospy.Time.now()
        self.last_distance = None

        # Publishers
        self.cmd_vel_pub = rospy.Publisher('/cmd_vel', Twist, queue_size=1)
        self.goal_reached_pub = rospy.Publisher('/nav/goal_reached', Bool, queue_size=1)
        self.current_pose_pub = rospy.Publisher('/nav/current_pose', PoseStamped, queue_size=1)
        self.stalled_pub = rospy.Publisher('/nav/progress_stalled', Bool, queue_size=1)

        # Subscribers - try both odom and ZED odom topics
        rospy.Subscriber('/odom', Odometry, self.odom_callback)
        # rospy.Subscriber('/zed2i/odom', Odometry, self.odom_callback)  # ZED camera odometry
        rospy.Subscriber('/nav/target_waypoint', PoseStamped, self.target_callback)

        # Control loop timer
        self.control_timer = rospy.Timer(rospy.Duration(1.0/self.control_frequency), self.control_loop)

        rospy.loginfo("Waypoint Controller initialized")
        rospy.loginfo("  Linear gain: {}, Angular gain: {}".format(self.linear_gain, self.angular_gain))
        rospy.loginfo("  Max velocities: {} m/s, {} rad/s".format(self.max_linear_vel, self.max_angular_vel))
        rospy.loginfo("  Goal tolerance: %.2f m, heading threshold: %.2f rad",
                      self.goal_tolerance, self.heading_threshold)

    def odom_callback(self, msg):
        """Update current pose from odometry"""
        # Extract position
        self.current_pose = msg.pose.pose

        # Publish for state machine
        pose_msg = PoseStamped()
        pose_msg.header = msg.header
        pose_msg.pose = self.current_pose
        self.current_pose_pub.publish(pose_msg)

    def target_callback(self, msg):
        """Receive new target waypoint"""
        self.target_waypoint = msg
        self.goal_reached = False
        self.last_distance = None
        self.last_progress_time = rospy.Time.now()
        rospy.loginfo("New target: ({:.2f}, {:.2f})".format(msg.pose.position.x, msg.pose.position.y))

    def get_yaw_from_quaternion(self, orientation):
        """Extract yaw angle from quaternion"""
        quaternion = (
            orientation.x,
            orientation.y,
            orientation.z,
            orientation.w
        )
        euler = tf.transformations.euler_from_quaternion(quaternion)
        return euler[2]  # yaw

    def normalize_angle(self, angle):
        """Normalize angle to [-pi, pi]"""
        while angle > math.pi:
            angle -= 2.0 * math.pi
        while angle < -math.pi:
            angle += 2.0 * math.pi
        return angle

    def calculate_control(self):
        """Calculate velocity commands using proportional control"""
        if self.current_pose is None or self.target_waypoint is None:
            return Twist()  # Zero velocity

        # Calculate distance and angle to target
        dx = self.target_waypoint.pose.position.x - self.current_pose.position.x
        dy = self.target_waypoint.pose.position.y - self.current_pose.position.y
        distance = math.sqrt(dx*dx + dy*dy)

        # Check if goal reached
        if distance < self.goal_tolerance:
            if not self.goal_reached:
                rospy.loginfo("Goal reached! Distance: {:.3f}m".format(distance))
                self.goal_reached = True
                self.goal_reached_pub.publish(Bool(data=True))
            return Twist()  # Stop

        # Calculate desired heading
        desired_yaw = math.atan2(dy, dx)
        current_yaw = self.get_yaw_from_quaternion(self.current_pose.orientation)
        yaw_error = self.normalize_angle(desired_yaw - current_yaw)

        # Proportional control
        cmd = Twist()

        # Angular velocity (turn towards target)
        cmd.angular.z = self.angular_gain * yaw_error
        cmd.angular.z = max(-self.max_angular_vel, min(self.max_angular_vel, cmd.angular.z))

        # Linear velocity: only advance once mostly aligned with the goal.
        if abs(yaw_error) < self.heading_threshold:
            cmd.linear.x = self.linear_gain * distance
            cmd.linear.x = max(0, min(self.max_linear_vel, cmd.linear.x))
        else:
            cmd.linear.x = self.turn_in_place_linear_vel

        # Check for stalled progress
        if self.last_distance is not None:
            if abs(self.last_distance - distance) < self.progress_epsilon:
                time_since_progress = (rospy.Time.now() - self.last_progress_time).to_sec()
                if time_since_progress > self.stall_timeout:
                    rospy.logwarn("Progress stalled! Distance: {:.2f}m".format(distance))
                    self.stalled_pub.publish(Bool(data=True))
            else:
                self.last_progress_time = rospy.Time.now()

        self.last_distance = distance

        return cmd

    def control_loop(self, event):
        """Main control loop - called at fixed frequency"""
        cmd = self.calculate_control()
        self.cmd_vel_pub.publish(cmd)

    def run(self):
        """Keep node running"""
        rospy.spin()


if __name__ == '__main__':
    try:
        controller = WaypointController()
        controller.run()
    except rospy.ROSInterruptException:
        pass
