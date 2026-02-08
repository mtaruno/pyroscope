#!/usr/bin/env python

"""
Simple motor test script
Press keys to test different movements
"""

import rospy
from geometry_msgs.msg import Twist
import sys
import termios
import tty


def get_key():
    """Get a single keypress from terminal"""
    tty.setraw(sys.stdin.fileno())
    key = sys.stdin.read(1)
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
    return key


if __name__ == '__main__':
    # Save terminal settings
    settings = termios.tcgetattr(sys.stdin)

    rospy.init_node('motor_tester')
    pub = rospy.Publisher('/cmd_vel', Twist, queue_size=1)
    rate = rospy.Rate(10)

    print("\n=== Motor Test ===")
    print("Controls:")
    print("  w: Forward")
    print("  s: Backward")
    print("  a: Turn left")
    print("  d: Turn right")
    print("  u: Left track only")
    print("  i: Right track only")
    print("  j: Left track backward")
    print("  k: Right track backward")
    print("  x: Stop")
    print("  q: Quit")
    print("\nPress a key...\n")

    try:
        while not rospy.is_shutdown():
            key = get_key()
            cmd = Twist()

            if key == 'w':
                print("Forward")
                cmd.linear.x = 0.2
            elif key == 's':
                print("Backward")
                cmd.linear.x = -0.2
            elif key == 'a':
                print("Turn left")
                cmd.angular.z = 0.5
            elif key == 'd':
                print("Turn right")
                cmd.angular.z = -0.5
            elif key == 'u':
                print("Left track forward only")
                cmd.linear.x = 0.15
                cmd.angular.z = -0.3  # Turn right to move left track more
            elif key == 'i':
                print("Right track forward only")
                cmd.linear.x = 0.15
                cmd.angular.z = 0.3   # Turn left to move right track more
            elif key == 'j':
                print("Left track backward only")
                cmd.linear.x = -0.15
                cmd.angular.z = 0.3   # Turn left while going backward
            elif key == 'k':
                print("Right track backward only")
                cmd.linear.x = -0.15
                cmd.angular.z = -0.3  # Turn right while going backward
            elif key == 'x':
                print("Stop")
                cmd = Twist()
            elif key == 'q':
                print("Quit")
                break
            else:
                print("Unknown key: {}".format(key))
                continue

            pub.publish(cmd)
            rate.sleep()

    except Exception as e:
        print(e)

    finally:
        # Stop robot and restore terminal
        pub.publish(Twist())
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
        print("\nMotor test stopped")
