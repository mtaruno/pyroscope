#!/usr/bin/env python3
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
from cv_bridge import CVBridge
import threading
import time

class SensorBridge:
    def __init__(self):
        rospy.init_node('sensor_bridge', anonymous=True)

        self.bridge = CVBridge()

        # Shared data file path (FastAPI will read this)
        self.data_dir = os.path.expanduser('~/Dev/pyroscope/application/backend/sensor_data')
        os.makedirs(self.data_dir, exist_ok=True)

        self.data_file = os.path.join(self.data_dir, 'latest_sensors.json')
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
        rospy.Subscriber('/sensors/sht40/temperature', Float64, self.temperature_callback)
        rospy.Subscriber('/sensors/sht40/humidity', Float64, self.humidity_callback)
        rospy.Subscriber('/sensors/thermal/mean', Float64, self.thermal_mean_callback)
        rospy.Subscriber('/sensors/thermal/image', Image, self.thermal_image_callback)
        rospy.Subscriber('/camera/color/image_raw', Image, self.rgb_image_callback)

        rospy.loginfo("Sensor bridge started - listening to sensor topics")

        # Start background thread to periodically save data
        self.save_thread = threading.Thread(target=self.save_loop, daemon=True)
        self.save_thread.start()

    def temperature_callback(self, msg):
        with self.lock:
            self.sensor_data['temperature'] = round(msg.data, 2)
            self.sensor_data['timestamp'] = time.time()

    def humidity_callback(self, msg):
        with self.lock:
            self.sensor_data['humidity'] = round(msg.data, 2)
            self.sensor_data['timestamp'] = time.time()

    def thermal_mean_callback(self, msg):
        with self.lock:
            self.sensor_data['thermal_mean'] = round(msg.data, 2)
            self.sensor_data['timestamp'] = time.time()

    def thermal_image_callback(self, msg):
        try:
            # Convert ROS Image to OpenCV format
            cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='passthrough')

            # Normalize thermal image for display (assuming 16-bit or float)
            if cv_image.dtype == np.uint16 or cv_image.dtype == np.float32:
                # Normalize to 0-255
                cv_image = cv2.normalize(cv_image, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)

            # Apply colormap for better visualization
            thermal_colored = cv2.applyColorMap(cv_image, cv2.COLORMAP_JET)

            # Save as JPEG
            cv2.imwrite(self.thermal_image_path, thermal_colored)

            with self.lock:
                self.sensor_data['thermal_image_url'] = '/api/sensors/thermal/image'
                self.sensor_data['timestamp'] = time.time()

            rospy.loginfo_throttle(5, f"Thermal image saved: {cv_image.shape}")
        except Exception as e:
            rospy.logerr(f"Failed to process thermal image: {e}")

    def rgb_image_callback(self, msg):
        try:
            # Convert ROS Image to OpenCV format
            cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

            # Save as JPEG
            cv2.imwrite(self.rgb_image_path, cv_image)

            with self.lock:
                self.sensor_data['rgb_image_url'] = '/api/sensors/rgb/image'
                self.sensor_data['timestamp'] = time.time()

            rospy.loginfo_throttle(5, f"RGB image saved: {cv_image.shape}")
        except Exception as e:
            rospy.logerr(f"Failed to process RGB image: {e}")

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
                rospy.logerr(f"Failed to save sensor data: {e}")

            rate.sleep()

    def spin(self):
        rospy.spin()


if __name__ == '__main__':
    try:
        bridge = SensorBridge()
        bridge.spin()
    except rospy.ROSInterruptException:
        pass
