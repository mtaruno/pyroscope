"""
ROS subscriber bridge: subscribe to /sensors/sht40/* and /sensors/thermal/* on Jetson,
cache latest values so waypoint_capture_service can read them (no subprocess).
Run only when ROS_MASTER_URI is set; runs in a background thread.
"""

import os
import threading
from typing import Optional, Dict, Any

_ros_cache: Dict[str, Any] = {
    "temperature": None,
    "humidity": None,
    "thermal_mean": None,
    "thermal_image_path": None,
    "lock": threading.Lock(),
}
_ros_thread: Optional[threading.Thread] = None
_ros_stop = threading.Event()


def _ros_subscriber_thread(thermal_image_save_dir: str):
    """Run rospy node and subscribe to sensor topics; update _ros_cache."""
    try:
        import rospy
        from std_msgs.msg import Float64
        from sensor_msgs.msg import Image
    except ImportError as e:
        import logging
        logging.getLogger(__name__).warning("rospy not available, ROS sensor bridge disabled: %s", e)
        return

    try:
        from cv_bridge import CvBridge
        bridge = CvBridge()
    except ImportError:
        bridge = None

    def cb_temp(msg):
        with _ros_cache["lock"]:
            _ros_cache["temperature"] = msg.data

    def cb_hum(msg):
        with _ros_cache["lock"]:
            _ros_cache["humidity"] = msg.data

    def cb_thermal_mean(msg):
        with _ros_cache["lock"]:
            _ros_cache["thermal_mean"] = msg.data

    def cb_thermal_image(msg):
        if not bridge:
            return
        try:
            import cv2
            cv_img = bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")
            if cv_img is not None:
                path = os.path.join(thermal_image_save_dir, "ros_latest.jpg")
                cv2.imwrite(path, cv_img)
                with _ros_cache["lock"]:
                    _ros_cache["thermal_image_path"] = path
        except Exception:
            pass

    rospy.init_node("waypoint_capture_bridge", anonymous=True, disable_signals=True)
    rospy.Subscriber("/sensors/sht40/temperature", Float64, cb_temp, queue_size=1)
    rospy.Subscriber("/sensors/sht40/humidity", Float64, cb_hum, queue_size=1)
    rospy.Subscriber("/sensors/thermal/mean", Float64, cb_thermal_mean, queue_size=1)
    if bridge:
        rospy.Subscriber("/sensors/thermal/image", Image, cb_thermal_image, queue_size=1)

    rate = rospy.Rate(2)
    while not _ros_stop.is_set() and not rospy.is_shutdown():
        rate.sleep()
    rospy.signal_shutdown("bridge stop")


def start_ros_bridge(thermal_image_save_dir: str) -> bool:
    """Start the ROS subscriber thread if ROS_MASTER_URI is set. Return True if using ROS."""
    global _ros_thread
    from app.config import settings
    uri = (settings.ROS_MASTER_URI or os.environ.get("ROS_MASTER_URI") or "").strip()
    if not uri:
        return False
    if _ros_thread is not None and _ros_thread.is_alive():
        return True
    os.environ["ROS_MASTER_URI"] = uri
    if getattr(settings, "ROS_IP", None) or os.environ.get("ROS_IP"):
        os.environ["ROS_IP"] = (settings.ROS_IP or os.environ.get("ROS_IP", ""))
    _ros_stop.clear()
    _ros_thread = threading.Thread(
        target=_ros_subscriber_thread,
        args=(thermal_image_save_dir,),
        daemon=True,
    )
    _ros_thread.start()
    return True


def stop_ros_bridge():
    _ros_stop.set()
    global _ros_thread
    if _ros_thread:
        _ros_thread.join(timeout=3)
        _ros_thread = None


def get_latest_from_ros() -> Dict[str, Any]:
    """Return latest cached sensor values from ROS (temperature, humidity, thermal_mean, thermal_image_path)."""
    with _ros_cache["lock"]:
        return {
            "temperature": _ros_cache["temperature"],
            "humidity": _ros_cache["humidity"],
            "thermal_mean": _ros_cache["thermal_mean"],
            "thermal_image_path": _ros_cache["thermal_image_path"],
        }


def is_ros_configured() -> bool:
    from app.config import settings
    uri = (settings.ROS_MASTER_URI or os.environ.get("ROS_MASTER_URI") or "").strip()
    return bool(uri)
