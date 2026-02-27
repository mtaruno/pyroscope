#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ROS Sensor Bridge - Subscribes to sensor topics and makes data available to FastAPI backend
Saves latest sensor values to JSON file for API to read
"""
import rospy
import json
import os
import cv2
import numpy as np
from std_msgs.msg import Float64
from sensor_msgs.msg import Image
# CVBridge not available - using manual conversion
import threading
import time

try:
    import serial
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

# Arduino serial port for SHT40 sensor (same as sht40_reader.py)
SHT40_PORT = "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0"
SHT40_BAUD = 9600


class SensorBridge:
    def __init__(self):
        rospy.init_node('sensor_bridge', anonymous=True)

        # CVBridge not needed - using manual image conversion

        # Shared data file path (FastAPI will read this)
        self.data_dir = os.path.expanduser('~/Dev/pyroscope/application/backend/sensor_data')
        rospy.loginfo("Sensor data directory: %s" % self.data_dir)
        if not os.path.exists(self.data_dir):
            rospy.loginfo("Creating directory: %s" % self.data_dir)
            os.makedirs(self.data_dir)

        self.data_file = os.path.join(self.data_dir, 'latest_sensors.json')
        rospy.loginfo("Sensor data file: %s" % self.data_file)
        self.thermal_image_path = os.path.join(self.data_dir, 'thermal_latest.jpg')
        self.rgb_image_path = os.path.join(self.data_dir, 'rgb_latest.jpg')

        # Latest sensor values
        self.sensor_data = {
            'temperature': None,
            'humidity': None,
            'thermal_mean': None,
            'thermal_image_url': None,
            'rgb_image_url': None,
            'timestamp': None
        }

        self.lock = threading.Lock()

        # Subscribe to sensor topics
        rospy.loginfo("Subscribing to sensor topics...")
        rospy.Subscriber('/sensors/sht40/temperature', Float64, self.temperature_callback)
        rospy.loginfo("  [OK] /sensors/sht40/temperature")
        rospy.Subscriber('/sensors/sht40/humidity', Float64, self.humidity_callback)
        rospy.loginfo("  [OK] /sensors/sht40/humidity")
        rospy.Subscriber('/sensors/thermal/mean', Float64, self.thermal_mean_callback)
        rospy.loginfo("  [OK] /sensors/thermal/mean")
        # rospy.Subscriber('/sensors/thermal/image', Image, self.thermal_image_callback)
        # rospy.loginfo("  [OK] /sensors/thermal/image")
        rospy.Subscriber('/camera/color/image_raw', Image, self.rgb_image_callback)
        rospy.loginfo("  [OK] /camera/color/image_raw")

        rospy.loginfo("Sensor bridge started - listening to sensor topics (RGB camera enabled)")

        # Start background thread to periodically save data
        self.save_thread = threading.Thread(target=self.save_loop)
        self.save_thread.setDaemon(True)
        self.save_thread.start()

    def temperature_callback(self, msg):
        with self.lock:
            self.sensor_data['temperature'] = round(msg.data, 2)
            self.sensor_data['timestamp'] = time.time()
            rospy.loginfo_throttle(5, "Temperature: %.2f C" % msg.data)

    def humidity_callback(self, msg):
        with self.lock:
            self.sensor_data['humidity'] = round(msg.data, 2)
            self.sensor_data['timestamp'] = time.time()
            rospy.loginfo_throttle(5, "Humidity: %.2f %%" % msg.data)

    def thermal_mean_callback(self, msg):
        with self.lock:
            self.sensor_data['thermal_mean'] = round(msg.data, 2)
            self.sensor_data['timestamp'] = time.time()
            rospy.loginfo_throttle(5, "Thermal mean: %.2f C" % msg.data)

    # IMAGE SUPPORT TEMPORARILY DISABLED - uncomment when cv_bridge is available
    # def thermal_image_callback(self, msg):
    #     try:
    #         # Convert ROS Image to OpenCV format
    #         cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='passthrough')
    #
    #         # Normalize thermal image for display (assuming 16-bit or float)
    #         if cv_image.dtype == np.uint16 or cv_image.dtype == np.float32:
    #             # Normalize to 0-255
    #             cv_image = cv2.normalize(cv_image, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
    #
    #         # Apply colormap for better visualization
    #         thermal_colored = cv2.applyColorMap(cv_image, cv2.COLORMAP_JET)
    #
    #         # Save as JPEG
    #         cv2.imwrite(self.thermal_image_path, thermal_colored)
    #
    #         with self.lock:
    #             self.sensor_data['thermal_image_url'] = '/api/sensors/thermal/image'
    #             self.sensor_data['timestamp'] = time.time()
    #
    #         rospy.loginfo_throttle(5, "Thermal image saved: %s" % str(cv_image.shape))
    #     except Exception as e:
    #         rospy.logerr("Failed to process thermal image: %s" % str(e))

    def rgb_image_callback(self, msg):
        try:
            # Manual conversion without CVBridge
            # Convert ROS Image message to numpy array
            if msg.encoding == 'bgr8' or msg.encoding == 'rgb8':
                # 8-bit color image
                img_data = np.frombuffer(msg.data, dtype=np.uint8)
                cv_image = img_data.reshape(msg.height, msg.width, 3)

                # If RGB, convert to BGR for OpenCV
                if msg.encoding == 'rgb8':
                    cv_image = cv2.cvtColor(cv_image, cv2.COLOR_RGB2BGR)
            else:
                rospy.logwarn("Unsupported encoding: %s" % msg.encoding)
                return

            # Save as JPEG
            cv2.imwrite(self.rgb_image_path, cv_image)

            with self.lock:
                self.sensor_data['rgb_image_url'] = '/api/sensors/rgb/image'
                self.sensor_data['timestamp'] = time.time()

            rospy.loginfo_throttle(5, "RGB image saved: %s" % str(cv_image.shape))
        except Exception as e:
            rospy.logerr("Failed to process RGB image: %s" % str(e))

    def save_loop(self):
        """Periodically save sensor data to JSON file"""
        rate = rospy.Rate(2)  # 2 Hz
        while not rospy.is_shutdown():
            try:
                with self.lock:
                    data_copy = self.sensor_data.copy()

                # Save to JSON file
                with open(self.data_file, 'w') as f:
                    json.dump(data_copy, f, indent=2)

            except Exception as e:
                rospy.logerr("Failed to save sensor data: %s" % str(e))

            rate.sleep()

    def spin(self):
        rospy.spin()


if __name__ == '__main__':
    try:
        bridge = SensorBridge()
        bridge.spin()
    except rospy.ROSInterruptException:
        pass
