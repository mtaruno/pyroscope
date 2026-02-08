#!/usr/bin/env python
# encoding: utf-8
# Copyright (c) 2011, Willow Garage, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in the
#      documentation and/or other materials provided with the distribution.
#    * Neither the name of the Willow Garage, Inc. nor the names of its
#      contributors may be used to endorse or promote products derived from
#       this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES LOSS OF USE, DATA, OR PROFITS OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import rospy
from geometry_msgs.msg import Twist
import sys, select, termios, tty

msg = """
Control Your SLAM-Bot!
---------------------------
Moving around:
   u    i    o
   j    k    l
   m    ,    .

q/z : increase/decrease max speeds by 10%
w/x : increase/decrease only linear speed by 10%
e/c : increase/decrease only angular speed by 10%
space key, k : force stop
anything else : stop smoothly

CTRL-C to quit
"""

moveBindings = {
    'i': (1, 0),
    'o': (1, -1),
    'j': (0, 1),
    'l': (0, -1),
    'u': (1, 1),
    ',': (-1, 0),
    '.': (-1, 1),
    'm': (-1, -1),
    'I': (1, 0),
    'O': (1, -1),
    'J': (0, 1),
    'L': (0, -1),
    'U': (1, 1),
    'M': (-1, -1),
}

speedBindings = {
    'Q': (1.1, 1.1),
    'Z': (.9, .9),
    'W': (1.1, 1),
    'X': (.9, 1),
    'E': (1, 1.1),
    'C': (1, .9),
    'q': (1.1, 1.1),
    'z': (.9, .9),
    'w': (1.1, 1),
    'x': (.9, 1),
    'e': (1, 1.1),
    'c': (1, .9),
}


def getKey():
    # tty.setraw():���ļ�������fdģʽ����Ϊraw��fileno():����һ�����ε��ļ�������(fd)
    tty.setraw(sys.stdin.fileno())
    # select():ֱ�ӵ��ò���ϵͳ��IO�ӿڣ�������д�fileno()�������ļ����
    rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
    # ��ȡһ���ֽڵ�������
    if rlist: key = sys.stdin.read(1)
    else: key = ''
    # tcsetattr�����������ļ�������fd��tty����
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
    return key


def vels(speed, turn):
    return "currently:\tspeed %s\tturn %s " % (speed, turn)


if __name__ == "__main__":
    settings = termios.tcgetattr(sys.stdin)
    rospy.init_node('transbot_keyboard')
    linear_limit = rospy.get_param('~linear_limit', 0.45)
    angular_limit = rospy.get_param('~angular_limit', 2.0)
    pub = rospy.Publisher('/cmd_vel', Twist, queue_size=1)
    (speed, turn) = (0.2, 1.0)
    (x, th) = (0, 0)
    status = 0
    count = 0
    try:
        print(msg)
        print(vels(speed, turn))
        while (1):
            # ��ȡ��ǰ������Ϣ
            key = getKey()
            # �����ַ����ж��Ƿ����ƶ��ֵ���
            if key in moveBindings.keys():
                x = moveBindings[key][0]
                th = moveBindings[key][1]
                count = 0
            # �����ַ����ж��Ƿ����ٶ��ֵ���
            elif key in speedBindings.keys():
                speed = speed * speedBindings[key][0]
                turn = turn * speedBindings[key][1]
                count = 0
                # �ٶ�����
                if speed > linear_limit: speed = linear_limit
                if turn > angular_limit: turn = angular_limit
                print(vels(speed, turn))
                # �ۼ�һ�������δ�ӡһ��msg��Ϣ
                if (status == 14): print(msg)
                status = (status + 1) % 15
            # ���������' '����'k'����ֹͣ�˶�
            elif key == ' ': (x, th) = (0, 0)
            else:
                # ����������ǳ�����ֹͣ�˶�����
                count = count + 1
                if count > 4: (x, th) = (0, 0)
                if (key == '\x03'): break
            # ������Ϣ
            twist = Twist()
            twist.linear.x = speed * x
            twist.angular.z = turn * th
            pub.publish(twist)
    except Exception as e: print(e)
    finally: pub.publish(Twist())
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)

