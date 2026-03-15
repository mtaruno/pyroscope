#!/usr/bin/env python3
"""
ROS node: read thermal camera once per period, publish mean to /sensors/thermal/mean
and optional image to /sensors/thermal/image. Run on Jetson.
"""

from __future__ import print_function
import os
import sys
import rospy
from std_msgs.msg import Float64
from sensor_msgs.msg import Image
from std_msgs.msg import Header


def cv2_to_ros_image(cv2_img, encoding="bgr8", frame_id="thermal"):
    """Build sensor_msgs/Image from OpenCV image without cv_bridge (Python 3 safe)."""
    if cv2_img is None or cv2_img.size == 0:
        return None
    height, width = cv2_img.shape[:2]
    if len(cv2_img.shape) == 2:
        step = width
        encoding = "mono8"
    else:
        step = width * cv2_img.shape[2]
    msg = Image()
    msg.header = Header(stamp=rospy.Time.now(), frame_id=frame_id)
    msg.height = height
    msg.width = width
    msg.encoding = encoding
    msg.is_bigendian = 0
    msg.step = step
    msg.data = cv2_img.tobytes()
    return msg

def _add_pyroscope_path():
    root = rospy.get_param("~pyroscope_root", "")
    if not root:
        try:
            import rospkg
            rp = rospkg.RosPack()
            pkg_path = rp.get_path("pyroscope_sensors")
            root = os.path.abspath(os.path.join(pkg_path, "..", "..", "..", ".."))
        except Exception:
            root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    if root and root not in sys.path:
        sys.path.insert(0, root)

# Must init_node first so that ~pyroscope_root param is resolvable (launch sets /thermal_node/pyroscope_root)
rospy.init_node("thermal_node", anonymous=False)
_add_pyroscope_path()

try:
    from thermal_capture import capture_once
except ImportError as e:
    rospy.logerr("Cannot import thermal_capture: %s. Set ~pyroscope_root.", e)
    sys.exit(1)


def main():
    rate_hz = rospy.get_param("~rate", 0.33)  # ~every 3 s
    publish_image = rospy.get_param("~publish_image", True)
    simulate = rospy.get_param("~simulate", False)

    pub_mean = rospy.Publisher("/sensors/thermal/mean", Float64, queue_size=1)
    pub_image = rospy.Publisher("/sensors/thermal/image", Image, queue_size=1) if publish_image else None

    rate = rospy.Rate(rate_hz)
    rospy.loginfo("Thermal node publishing mean at %.2f Hz (image=%s, simulate=%s)",
                  rate_hz, pub_image is not None, simulate)

    while not rospy.is_shutdown():
        try:
            image_path = "/tmp/thermal_latest.jpg" if pub_image else None
            result = capture_once(save_image_path=image_path, simulate=simulate)
            mean = result.get("thermal_mean")
            if mean is not None:
                pub_mean.publish(Float64(data=float(mean)))
            if pub_image and result.get("image_path") and os.path.exists(result["image_path"]):
                import cv2
                img = cv2.imread(result["image_path"])
                if img is not None:
                    msg = cv2_to_ros_image(img, encoding="bgr8", frame_id="thermal")
                    if msg is not None:
                        pub_image.publish(msg)
        except Exception as e:
            rospy.logerr_throttle(5, "Thermal capture failed: %s", e)
        rate.sleep()


if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        pass
