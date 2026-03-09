"""
ROS subscriber bridge: subscribe to sensor topics on Jetson, cache latest values.
Subscribed topics:
  /sensors/sht40/temperature   (std_msgs/Float64)
  /sensors/sht40/humidity      (std_msgs/Float64)
  /sensors/thermal/mean        (std_msgs/Float64)
  /sensors/thermal/image       (sensor_msgs/Image)
  /camera/color/image_raw      (sensor_msgs/Image)  -- RealSense D435i RGB
  /coverage/capture_ready      (std_msgs/Bool)      -- True triggers one capture
Run only when ROS_MASTER_URI is set; runs in a background thread.
"""

import os
import threading
from typing import Optional, Dict, Any

REQUIRED_SENSOR_TOPICS = [
    "/sensors/sht40/temperature",
    "/sensors/sht40/humidity",
    "/sensors/thermal/mean",
    "/camera/color/image_raw",
]

_ros_cache: Dict[str, Any] = {
    "temperature": None,
    "humidity": None,
    "thermal_mean": None,
    "thermal_image_path": None,
    "rgb_image_path": None,
    "voltage": None,
    "battery_percent": None,
    "capture_ready_queue": [],
    "lock": threading.Lock(),
    "capture_ready_condition": threading.Condition(),
}
_ros_thread: Optional[threading.Thread] = None
_ros_stop = threading.Event()


def voltage_to_percent(voltage: float) -> int:
    """3S LiPo mapping: 9.6V -> 0%, 12.6V -> 100% (clamped)."""
    try:
        percent = ((float(voltage) - 9.6) / (12.6 - 9.6)) * 100.0
    except Exception:
        return 0
    return max(0, min(100, int(round(percent))))


def _ros_subscriber_thread(thermal_image_save_dir: str, rgb_image_save_dir: str):
    """Run rospy node and subscribe to sensor topics; update _ros_cache."""
    try:
        import rospy
        from std_msgs.msg import Float64, Float32, Bool
        from sensor_msgs.msg import Image
    except ImportError as e:
        import logging
        logging.getLogger(__name__).warning("rospy not available, ROS sensor bridge disabled: %s", e)
        return

    # Image conversion: prefer cv_bridge, fall back to numpy+Pillow
    _use_cv_bridge = False
    try:
        from cv_bridge import CvBridge
        import cv2 as _cv2
        _bridge = CvBridge()
        _use_cv_bridge = True
    except ImportError:
        _bridge = None
        _cv2 = None
    try:
        import numpy as np
        from PIL import Image as PILImage
        _use_pil = True
    except ImportError:
        _use_pil = False
    can_save_images = _use_cv_bridge or _use_pil
    try:
        from transbot_msgs.msg import Battery as TransbotBattery
    except ImportError:
        TransbotBattery = None

    def cb_temp(msg):
        with _ros_cache["lock"]:
            _ros_cache["temperature"] = msg.data

    def cb_hum(msg):
        with _ros_cache["lock"]:
            _ros_cache["humidity"] = msg.data

    def cb_thermal_mean(msg):
        with _ros_cache["lock"]:
            _ros_cache["thermal_mean"] = msg.data

    def _save_ros_image(msg, save_path, encoding="passthrough"):
        """Convert sensor_msgs/Image to JPEG. Uses cv_bridge if available, else numpy+Pillow."""
        try:
            if _use_cv_bridge:
                cv_img = _bridge.imgmsg_to_cv2(msg, desired_encoding=encoding)
                if cv_img is not None:
                    _cv2.imwrite(save_path, cv_img)
                    return True
            elif _use_pil:
                # Parse raw ROS Image data with numpy + Pillow
                channels = len(msg.data) // (msg.width * msg.height) if msg.width and msg.height else 3
                arr = np.frombuffer(msg.data, dtype=np.uint8).reshape((msg.height, msg.width, channels))
                # ROS typically publishes BGR8; Pillow expects RGB
                if msg.encoding in ("bgr8", "8UC3") or (encoding == "bgr8" and channels == 3):
                    arr = arr[:, :, ::-1]  # BGR → RGB
                pil_img = PILImage.fromarray(arr)
                pil_img.save(save_path, "JPEG", quality=85)
                return True
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug("Image save failed: %s", e)
        return False

    def cb_thermal_image(msg):
        path = os.path.join(thermal_image_save_dir, "ros_latest.jpg")
        if _save_ros_image(msg, path):
            with _ros_cache["lock"]:
                _ros_cache["thermal_image_path"] = path

    def cb_rgb_image(msg):
        """Cache latest RealSense D435i color frame as JPEG."""
        path = os.path.join(rgb_image_save_dir, "ros_latest.jpg")
        if _save_ros_image(msg, path, encoding="bgr8"):
            with _ros_cache["lock"]:
                _ros_cache["rgb_image_path"] = path

    def cb_capture_ready(msg):
        # Consume only True events; each True means "capture once".
        if msg.data is not True:
            return
        with _ros_cache["capture_ready_condition"]:
            _ros_cache["capture_ready_queue"].append(True)
            _ros_cache["capture_ready_condition"].notify_all()

    def _set_voltage(voltage_value):
        with _ros_cache["lock"]:
            _ros_cache["voltage"] = voltage_value
            _ros_cache["battery_percent"] = voltage_to_percent(voltage_value)

    def cb_voltage_float(msg):
        try:
            _set_voltage(float(msg.data))
        except Exception:
            pass

    def cb_voltage_battery(msg):
        try:
            value = getattr(msg, "Voltage", None)
            if value is None:
                value = getattr(msg, "voltage", None)
            if value is None:
                return
            _set_voltage(float(value))
        except Exception:
            pass

    rospy.init_node("waypoint_capture_bridge", anonymous=True, disable_signals=True)
    rospy.Subscriber("/sensors/sht40/temperature", Float64, cb_temp, queue_size=1)
    rospy.Subscriber("/sensors/sht40/humidity", Float64, cb_hum, queue_size=1)
    rospy.Subscriber("/sensors/thermal/mean", Float64, cb_thermal_mean, queue_size=1)
    rospy.Subscriber("/coverage/capture_ready", Bool, cb_capture_ready, queue_size=50)
    topic_types = {}
    try:
        topic_types = {name: t for name, t in rospy.get_published_topics()}
    except Exception:
        topic_types = {}
    voltage_type = topic_types.get("/voltage")
    if voltage_type == "transbot_msgs/Battery" and TransbotBattery is not None:
        rospy.Subscriber("/voltage", TransbotBattery, cb_voltage_battery, queue_size=1)
    elif voltage_type == "std_msgs/Float32":
        rospy.Subscriber("/voltage", Float32, cb_voltage_float, queue_size=1)
    else:
        rospy.Subscriber("/voltage", Float64, cb_voltage_float, queue_size=1)
    if can_save_images:
        rospy.Subscriber("/sensors/thermal/image", Image, cb_thermal_image, queue_size=1)
        rospy.Subscriber("/camera/color/image_raw", Image, cb_rgb_image, queue_size=1)

    rate = rospy.Rate(2)
    while not _ros_stop.is_set() and not rospy.is_shutdown():
        rate.sleep()
    rospy.signal_shutdown("bridge stop")


def start_ros_bridge(thermal_image_save_dir: str, rgb_image_save_dir: str) -> bool:
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
        args=(thermal_image_save_dir, rgb_image_save_dir),
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
    """Return latest cached sensor values from ROS."""
    with _ros_cache["lock"]:
        return {
            "temperature": _ros_cache["temperature"],
            "humidity": _ros_cache["humidity"],
            "thermal_mean": _ros_cache["thermal_mean"],
            "thermal_image_path": _ros_cache["thermal_image_path"],
            "rgb_image_path": _ros_cache["rgb_image_path"],
            "voltage": _ros_cache["voltage"],
            "battery_percent": _ros_cache["battery_percent"],
        }


def wait_for_next_capture_ready(timeout_sec: float = 0.5) -> bool:
    """Wait and consume one capture trigger from /coverage/capture_ready."""
    condition = _ros_cache["capture_ready_condition"]
    with condition:
        if not _ros_cache["capture_ready_queue"]:
            condition.wait(timeout=timeout_sec)
        if not _ros_cache["capture_ready_queue"]:
            return False
        _ros_cache["capture_ready_queue"].pop(0)
        return True


def clear_capture_ready_queue() -> None:
    condition = _ros_cache["capture_ready_condition"]
    with condition:
        _ros_cache["capture_ready_queue"].clear()


def is_ros_configured() -> bool:
    from app.config import settings
    uri = (settings.ROS_MASTER_URI or os.environ.get("ROS_MASTER_URI") or "").strip()
    return bool(uri)


def get_required_topics_status() -> Dict[str, Any]:
    """Check whether required sensor topics currently exist on ROS master."""
    status = {"available": False, "missing_topics": list(REQUIRED_SENSOR_TOPICS)}
    if not is_ros_configured():
        return status
    try:
        import rospy
        published = rospy.get_published_topics()
        published_names = {item[0] for item in published}
        missing = [topic for topic in REQUIRED_SENSOR_TOPICS if topic not in published_names]
        return {
            "available": len(missing) == 0,
            "missing_topics": missing,
        }
    except Exception:
        return status
