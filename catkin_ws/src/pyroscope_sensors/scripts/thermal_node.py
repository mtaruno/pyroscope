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
try:
    from cv_bridge import CvBridge
    HAS_CV_BRIDGE = True
except ImportError:
    HAS_CV_BRIDGE = False
    CvBridge = None

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

_add_pyroscope_path()

try:
    from thermal_capture import capture_once
except ImportError as e:
    rospy.logerr("Cannot import thermal_capture: %s. Set ~pyroscope_root.", e)
    sys.exit(1)


def main():
    rospy.init_node("thermal_node", anonymous=False)
    rate_hz = rospy.get_param("~rate", 0.33)  # ~every 3 s
    publish_image = rospy.get_param("~publish_image", True)
    simulate = rospy.get_param("~simulate", False)

    pub_mean = rospy.Publisher("/sensors/thermal/mean", Float64, queue_size=1)
    pub_image = None
    bridge = None
    if publish_image and HAS_CV_BRIDGE and CvBridge:
        try:
            bridge = CvBridge()
            pub_image = rospy.Publisher("/sensors/thermal/image", Image, queue_size=1)
        except Exception as e:
            rospy.logwarn("cv_bridge not available, thermal image will not be published: %s", e)

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
            if pub_image and bridge and result.get("image_path") and os.path.exists(result["image_path"]):
                import cv2
                img = cv2.imread(result["image_path"])
                if img is not None:
                    msg = bridge.cv2_to_imgmsg(img, encoding="bgr8")
                    msg.header.stamp = rospy.Time.now()
                    msg.header.frame_id = "thermal"
                    pub_image.publish(msg)
        except Exception as e:
            rospy.logerr_throttle(5, "Thermal capture failed: %s", e)
        rate.sleep()


if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        pass
