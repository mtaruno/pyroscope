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

Live images are cached as in-memory JPEG bytes (no disk I/O).
Waypoint capture service handles its own disk saves for scan records.
"""

import io
import os
import logging
import re
import threading
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

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
    "thermal_image_bytes": None,   # in-memory JPEG bytes
    "thermal_image_min": None,
    "thermal_image_max": None,
    "thermal_image_avg": None,
    "rgb_image_bytes": None,       # in-memory JPEG bytes
    "thermal_image_path": None,    # kept for waypoint capture compatibility
    "rgb_image_path": None,        # kept for waypoint capture compatibility
    "voltage": None,
    "battery_percent": None,
    "capture_ready_queue": [],
    "capture_ready_active": False,
    "coverage_complete": threading.Event(),  # set when /coverage/complete=true received
    "coverage_progress_message": None,
    "coverage_done_points": 0,
    "coverage_total_points": None,
    "coverage_percent": 0.0,
    "bridge_ready": threading.Event(),
    "bridge_error": None,
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


def get_live_rgb_bytes() -> Optional[bytes]:
    """Return latest RGB JPEG bytes from cache, or None."""
    with _ros_cache["lock"]:
        return _ros_cache["rgb_image_bytes"]


def get_live_thermal_bytes() -> Optional[bytes]:
    """Return latest thermal JPEG bytes from cache, or None."""
    with _ros_cache["lock"]:
        return _ros_cache["thermal_image_bytes"]


def save_live_rgb_to_file(dest_path: str) -> bool:
    """Write the current in-memory RGB JPEG to a file (for waypoint capture). Returns True on success."""
    jpeg_bytes = get_live_rgb_bytes()
    if jpeg_bytes is None:
        return False
    try:
        with open(dest_path, "wb") as f:
            f.write(jpeg_bytes)
        return True
    except Exception:
        return False


def save_live_thermal_to_file(dest_path: str) -> bool:
    """Write the current in-memory thermal JPEG to a file (for waypoint capture). Returns True on success."""
    jpeg_bytes = get_live_thermal_bytes()
    if jpeg_bytes is None:
        return False
    try:
        with open(dest_path, "wb") as f:
            f.write(jpeg_bytes)
        return True
    except Exception:
        return False


def _ros_subscriber_thread(thermal_image_save_dir: str, rgb_image_save_dir: str):
    """Run rospy node and subscribe to sensor topics; update _ros_cache."""
    try:
        import rospy
        from std_msgs.msg import Float64, Float32, Bool, String
        from sensor_msgs.msg import Image
    except ImportError as e:
        _ros_cache["bridge_error"] = str(e)
        _ros_cache["bridge_ready"].set()
        logger.warning("rospy not available, ROS sensor bridge disabled: %s", e)
        return

    # Image conversion: prefer cv_bridge+cv2, fall back to numpy+Pillow
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
        np = None
        PILImage = None
        _use_pil = False

    can_process_images = _use_cv_bridge or _use_pil
    logger.warning("Image pipeline: cv_bridge=%s, pil=%s, can_process=%s", _use_cv_bridge, _use_pil, can_process_images)

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

    def _ros_image_to_jpeg(
        msg,
        encoding="passthrough",
        colormap=None,
        rotate_90_clockwise=False,
        flip_horizontal=False,
    ):
        """Convert sensor_msgs/Image to JPEG bytes in memory.
        colormap: if set, apply a Matplotlib colormap to grayscale data (e.g. 'inferno').
        """
        try:
            if _use_cv_bridge:
                cv_img = _bridge.imgmsg_to_cv2(msg, desired_encoding=encoding)
                if cv_img is not None:
                    if colormap and len(cv_img.shape) == 2:
                        # Grayscale -> colormap via Pillow
                        pil_gray = PILImage.fromarray(cv_img)
                        pil_img = _apply_thermal_colormap(pil_gray, colormap)
                        if rotate_90_clockwise:
                            pil_img = pil_img.transpose(PILImage.Transpose.ROTATE_270)
                        if flip_horizontal:
                            pil_img = pil_img.transpose(PILImage.Transpose.FLIP_LEFT_RIGHT)
                        buf = io.BytesIO()
                        pil_img.save(buf, "JPEG", quality=85)
                        return buf.getvalue()
                    # Keep original RGB colors: cv2 expects BGR when encoding JPEG.
                    if len(cv_img.shape) == 3 and msg.encoding in ("rgb8", "rgb16"):
                        cv_img = cv_img[:, :, ::-1]
                    if rotate_90_clockwise:
                        cv_img = _cv2.rotate(cv_img, _cv2.ROTATE_90_CLOCKWISE)
                    if flip_horizontal:
                        cv_img = _cv2.flip(cv_img, 1)
                    _, buf = _cv2.imencode(".jpg", cv_img, [_cv2.IMWRITE_JPEG_QUALITY, 85])
                    return buf.tobytes()
            elif _use_pil:
                channels = len(msg.data) // (msg.width * msg.height) if msg.width and msg.height else 3
                if channels == 1:
                    arr = np.frombuffer(msg.data, dtype=np.uint8).reshape((msg.height, msg.width))
                else:
                    arr = np.frombuffer(msg.data, dtype=np.uint8).reshape((msg.height, msg.width, channels))
                if channels == 1 or msg.encoding == "mono8":
                    pil_gray = PILImage.fromarray(arr, mode="L")
                else:
                    pil_gray = None

                if pil_gray is not None:
                    if colormap:
                        pil_img = _apply_thermal_colormap(pil_gray, colormap)
                    else:
                        pil_img = pil_gray
                else:
                    if msg.encoding in ("bgr8", "8UC3") or (encoding == "bgr8" and channels == 3):
                        arr = arr[:, :, ::-1]  # BGR -> RGB
                    pil_img = PILImage.fromarray(arr)
                if rotate_90_clockwise:
                    pil_img = pil_img.transpose(PILImage.Transpose.ROTATE_270)
                if flip_horizontal:
                    pil_img = pil_img.transpose(PILImage.Transpose.FLIP_LEFT_RIGHT)
                buf = io.BytesIO()
                pil_img.save(buf, "JPEG", quality=85)
                return buf.getvalue()
        except Exception as e:
            logger.warning("Image encode failed (encoding=%s, %dx%d): %s", msg.encoding, msg.width, msg.height, e)
        return None

    def _apply_thermal_colormap(pil_gray, colormap_name="inferno"):
        """Apply a colormap to a grayscale PIL image, return RGB PIL image."""
        arr = np.array(pil_gray, dtype=np.float32)
        if arr.ndim != 2:
            return pil_gray.convert("RGB")

        # Piecewise thermal mapping in Celsius:
        # <=20C: pure blue
        # 20..33C: very gentle exponential move toward warm colors
        # 33..37C: rapidly move to red
        # >=37C: pure red
        t_blue = 20.0
        t_warm = 33.0
        t_red = 37.0

        r = np.zeros_like(arr, dtype=np.float32)
        g = np.zeros_like(arr, dtype=np.float32)
        b = np.zeros_like(arr, dtype=np.float32)

        cold_mask = arr <= t_blue
        r[cold_mask] = 0.0
        g[cold_mask] = 0.0
        b[cold_mask] = 255.0

        gentle_mask = (arr > t_blue) & (arr < t_warm)
        if np.any(gentle_mask):
            u = (arr[gentle_mask] - t_blue) / (t_warm - t_blue)
            u = np.clip(u, 0.0, 1.0)
            u = np.power(u, 2.4)
            # Blue -> warm orange/yellow base
            r[gentle_mask] = 255.0 * u
            g[gentle_mask] = 220.0 * u
            b[gentle_mask] = 255.0 * (1.0 - u)

        hot_mask = (arr >= t_warm) & (arr < t_red)
        if np.any(hot_mask):
            v = (arr[hot_mask] - t_warm) / (t_red - t_warm)
            v = np.clip(v, 0.0, 1.0)
            v = np.power(v, 0.35)
            r[hot_mask] = 255.0
            g[hot_mask] = 220.0 * (1.0 - v)
            b[hot_mask] = 0.0

        very_hot_mask = arr >= t_red
        r[very_hot_mask] = 255.0
        g[very_hot_mask] = 0.0
        b[very_hot_mask] = 0.0

        rgb = np.stack([r, g, b], axis=-1).astype(np.uint8)
        return PILImage.fromarray(rgb, mode="RGB")

    _rgb_logged = [False]
    _thermal_logged = [False]

    def cb_thermal_image(msg):
        # Thermal is temperature values; render with fixed Celsius color mapping.
        jpeg_bytes = _ros_image_to_jpeg(
            msg,
            encoding="passthrough",
            colormap="temperature",
            rotate_90_clockwise=True,
            flip_horizontal=True,
        )
        if jpeg_bytes:
            thermal_min = thermal_max = thermal_avg = None
            try:
                if np is not None:
                    thermal_arr = None
                    if _use_cv_bridge:
                        thermal_arr = _bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")
                    if thermal_arr is None:
                        dtype = np.uint8
                        if msg.encoding in ("32FC1", "32FC"):
                            dtype = np.float32
                        elif msg.encoding in ("16UC1", "mono16", "16SC1", "16SC"):
                            dtype = np.uint16
                        raw_arr = np.frombuffer(msg.data, dtype=dtype)
                        if raw_arr.size > 0 and msg.width and msg.height:
                            thermal_arr = raw_arr.reshape((msg.height, msg.width))
                    if thermal_arr is not None:
                        thermal_np = np.array(thermal_arr, dtype=np.float32)
                        if thermal_np.ndim == 3:
                            thermal_np = thermal_np[:, :, 0]
                        valid = np.isfinite(thermal_np)
                        if np.any(valid):
                            vals = thermal_np[valid]
                            thermal_min = float(np.min(vals))
                            thermal_max = float(np.max(vals))
                            thermal_avg = float(np.mean(vals))
            except Exception:
                pass
            with _ros_cache["lock"]:
                _ros_cache["thermal_image_bytes"] = jpeg_bytes
                _ros_cache["thermal_image_min"] = thermal_min
                _ros_cache["thermal_image_max"] = thermal_max
                _ros_cache["thermal_image_avg"] = thermal_avg
            if not _thermal_logged[0]:
                logger.warning("Thermal image streaming: %d bytes", len(jpeg_bytes))
                _thermal_logged[0] = True

    def cb_rgb_image(msg):
        jpeg_bytes = _ros_image_to_jpeg(msg, encoding="passthrough")
        if jpeg_bytes:
            with _ros_cache["lock"]:
                _ros_cache["rgb_image_bytes"] = jpeg_bytes
            if not _rgb_logged[0]:
                logger.warning("RGB image streaming: %d bytes (encoding=%s, %dx%d)", len(jpeg_bytes), msg.encoding, msg.width, msg.height)
                _rgb_logged[0] = True

    def cb_capture_ready(msg):
        with _ros_cache["capture_ready_condition"]:
            if msg.data is True:
                if not _ros_cache["capture_ready_active"]:
                    _ros_cache["capture_ready_queue"].append(True)
                    _ros_cache["capture_ready_condition"].notify_all()
                _ros_cache["capture_ready_active"] = True
            else:
                _ros_cache["capture_ready_active"] = False

    def cb_coverage_complete(msg):
        if msg.data is True:
            _ros_cache["coverage_complete"].set()
            logger.warning("Coverage mission complete signal received from planner")

    def cb_coverage_progress(msg):
        done_points = 0
        total_points = None
        percent = 0.0
        match = re.match(r"^\s*(\d+)\s*/\s*(\d+)\s+waypoints\s+\((\d+)%\)\s*$", msg.data or "")
        if match:
            done_points = int(match.group(1))
            total_points = int(match.group(2))
            percent = float(match.group(3))
        with _ros_cache["lock"]:
            _ros_cache["coverage_progress_message"] = msg.data
            _ros_cache["coverage_done_points"] = done_points
            _ros_cache["coverage_total_points"] = total_points
            _ros_cache["coverage_percent"] = percent

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
    rospy.Subscriber("/coverage/progress", String, cb_coverage_progress, queue_size=10)
    rospy.Subscriber("/coverage/complete", Bool, cb_coverage_complete, queue_size=1)
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
    if can_process_images:
        rospy.Subscriber("/sensors/thermal/image", Image, cb_thermal_image, queue_size=1)
        rospy.Subscriber("/camera/color/image_raw", Image, cb_rgb_image, queue_size=1)
        logger.warning("Subscribed to image topics (in-memory JPEG streaming)")
    else:
        logger.warning("NO image library available (need numpy+Pillow or cv_bridge+cv2). Image topics NOT subscribed.")

    _ros_cache["bridge_error"] = None
    _ros_cache["bridge_ready"].set()

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
    _ros_cache["bridge_error"] = None
    _ros_cache["bridge_ready"].clear()
    _ros_thread = threading.Thread(
        target=_ros_subscriber_thread,
        args=(thermal_image_save_dir, rgb_image_save_dir),
        daemon=True,
    )
    _ros_thread.start()
    _ros_cache["bridge_ready"].wait(timeout=3.0)
    return _ros_thread.is_alive() and _ros_cache["bridge_error"] is None


def stop_ros_bridge():
    _ros_stop.set()
    global _ros_thread
    if _ros_thread:
        _ros_thread.join(timeout=3)
        _ros_thread = None
    _ros_cache["bridge_ready"].clear()


def get_latest_from_ros() -> Dict[str, Any]:
    """Return latest cached sensor values from ROS."""
    with _ros_cache["lock"]:
        return {
            "temperature": _ros_cache["temperature"],
            "humidity": _ros_cache["humidity"],
            "thermal_mean": _ros_cache["thermal_mean"],
            "thermal_image_path": _ros_cache["thermal_image_path"],
            "thermal_image_min": _ros_cache["thermal_image_min"],
            "thermal_image_max": _ros_cache["thermal_image_max"],
            "thermal_image_avg": _ros_cache["thermal_image_avg"],
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
        _ros_cache["capture_ready_active"] = False
    _ros_cache["coverage_complete"].clear()
    with _ros_cache["lock"]:
        _ros_cache["coverage_progress_message"] = None
        _ros_cache["coverage_done_points"] = 0
        _ros_cache["coverage_total_points"] = None
        _ros_cache["coverage_percent"] = 0.0


def is_coverage_complete() -> bool:
    """Return True if /coverage/complete=true has been received since last clear."""
    return _ros_cache["coverage_complete"].is_set()


def get_coverage_progress() -> Dict[str, Any]:
    with _ros_cache["lock"]:
        return {
            "message": _ros_cache["coverage_progress_message"],
            "done_points": int(_ros_cache["coverage_done_points"] or 0),
            "total_points": _ros_cache["coverage_total_points"],
            "progress_percent": float(_ros_cache["coverage_percent"] or 0.0),
        }


def get_ros_bridge_error() -> Optional[str]:
    return _ros_cache["bridge_error"]


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
