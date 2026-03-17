import logging
import os
import threading
import time

from fastapi import HTTPException

from app.config import settings

logger = logging.getLogger(__name__)

TELEOP_PUBLISH_HZ = 15
TELEOP_DEADMAN_SEC = 0.6

_teleop_state = {
    "thread": None,
    "stop_event": threading.Event(),
    "ready_event": threading.Event(),
    "lock": threading.Lock(),
    "error": None,
    "linear_x": 0.0,
    "angular_z": 0.0,
    "deadline": 0.0,
}


def _configure_ros_env() -> None:
    uri = (settings.ROS_MASTER_URI or os.environ.get("ROS_MASTER_URI") or "").strip()
    if uri:
        os.environ["ROS_MASTER_URI"] = uri
    ros_ip = (settings.ROS_IP or os.environ.get("ROS_IP") or "").strip()
    if ros_ip:
        os.environ["ROS_IP"] = ros_ip


def _teleop_thread() -> None:
    try:
        import rospy
        from geometry_msgs.msg import Twist
        from std_msgs.msg import Bool
    except ImportError as e:
        _teleop_state["error"] = str(e)
        _teleop_state["ready_event"].set()
        logger.warning("rospy not available, persistent teleop bridge disabled: %s", e)
        return

    _configure_ros_env()

    try:
        if not rospy.core.is_initialized():
            rospy.init_node("pyroscope_teleop_bridge", anonymous=True, disable_signals=True)
    except Exception as e:
        _teleop_state["error"] = str(e)
        _teleop_state["ready_event"].set()
        logger.warning("Failed to initialize rospy teleop bridge: %s", e)
        return

    publisher = rospy.Publisher("/cmd_vel", Twist, queue_size=10)
    manual_override_pub = rospy.Publisher("/nav/manual_override", Bool, queue_size=10)
    rate = rospy.Rate(TELEOP_PUBLISH_HZ)
    zero_sent = False

    _teleop_state["error"] = None
    _teleop_state["ready_event"].set()

    while not _teleop_state["stop_event"].is_set() and not rospy.is_shutdown():
        now = time.monotonic()
        with _teleop_state["lock"]:
            linear_x = _teleop_state["linear_x"]
            angular_z = _teleop_state["angular_z"]
            deadline = _teleop_state["deadline"]

        active = now <= deadline and (abs(linear_x) > 1e-6 or abs(angular_z) > 1e-6)
        if active:
            twist = Twist()
            twist.linear.x = linear_x
            twist.angular.z = angular_z
            publisher.publish(twist)
            manual_override_pub.publish(Bool(data=True))
            zero_sent = False
        elif not zero_sent:
            publisher.publish(Twist())
            manual_override_pub.publish(Bool(data=False))
            zero_sent = True

        try:
            rate.sleep()
        except Exception:
            break


def _ensure_teleop_thread() -> bool:
    thread = _teleop_state["thread"]
    if thread is not None and thread.is_alive():
        return _teleop_state["error"] is None

    _teleop_state["stop_event"].clear()
    _teleop_state["ready_event"].clear()
    _teleop_state["error"] = None
    thread = threading.Thread(target=_teleop_thread, daemon=True)
    _teleop_state["thread"] = thread
    thread.start()
    _teleop_state["ready_event"].wait(timeout=3.0)
    return thread.is_alive() and _teleop_state["error"] is None


def publish_teleop_command(linear_x: float, angular_z: float) -> str:
    """Update the persistent teleop publisher. Return the transport used."""
    if not _ensure_teleop_thread():
        return _publish_teleop_fallback(linear_x, angular_z)

    with _teleop_state["lock"]:
        _teleop_state["linear_x"] = linear_x
        _teleop_state["angular_z"] = angular_z
        _teleop_state["deadline"] = (
            time.monotonic() + TELEOP_DEADMAN_SEC if abs(linear_x) > 1e-6 or abs(angular_z) > 1e-6 else 0.0
        )
    return "persistent_bridge"


def stop_teleop_bridge() -> None:
    with _teleop_state["lock"]:
        _teleop_state["linear_x"] = 0.0
        _teleop_state["angular_z"] = 0.0
        _teleop_state["deadline"] = 0.0

    _teleop_state["stop_event"].set()
    thread = _teleop_state["thread"]
    if thread is not None:
        thread.join(timeout=2.0)
    _teleop_state["thread"] = None
    _teleop_state["ready_event"].clear()


def _publish_teleop_fallback(linear_x: float, angular_z: float) -> str:
    twist_yaml = (
        "'{linear: {x: %.3f, y: 0, z: 0}, angular: {x: 0, y: 0, z: %.3f}}'"
        % (linear_x, angular_z)
    )
    ros_cmd = "source /opt/ros/melodic/setup.bash && rostopic pub -1 /cmd_vel geometry_msgs/Twist %s" % twist_yaml
    clean_env = {
        key: value
        for key, value in os.environ.items()
        if key not in ("VIRTUAL_ENV", "PYTHONHOME", "PYTHONPATH", "CONDA_DEFAULT_ENV")
    }
    try:
        import subprocess

        subprocess.Popen(["bash", "-c", ros_cmd], env=clean_env)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to send teleop: %s" % str(e))
    return "rostopic_fallback"
