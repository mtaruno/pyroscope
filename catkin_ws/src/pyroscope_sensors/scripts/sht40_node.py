#!/usr/bin/env python3
"""
ROS node: read SHT40 temperature and humidity, publish to /sensors/sht40/temperature and /sensors/sht40/humidity.
Run on Jetson; add pyroscope repo root to path so sht40_reader can be imported.
"""

from __future__ import print_function
import os
import sys
import rospy
from std_msgs.msg import Float64

# Add pyroscope repo root so we can import sht40_reader
def _add_pyroscope_path():
    root = rospy.get_param("~pyroscope_root", "")
    if not root:
        # Default: parent of catkin_ws (when running from source)
        try:
            import rospkg
            rp = rospkg.RosPack()
            pkg_path = rp.get_path("pyroscope_sensors")
            # pkg_path is .../src/pyroscope_sensors or .../share/pyroscope_sensors
            root = os.path.abspath(os.path.join(pkg_path, "..", "..", "..", ".."))
        except Exception:
            root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    if root and root not in sys.path:
        sys.path.insert(0, root)

# Must init_node first so that ~pyroscope_root param is resolvable (launch sets /sht40_node/pyroscope_root)
rospy.init_node("sht40_node", anonymous=False)
_add_pyroscope_path()

try:
    from sht40_reader import SHT40Sensor
except ImportError as e:
    rospy.logerr("Cannot import sht40_reader: %s. Run with pyroscope_root param or PYROSCOPE_ROOT env.", e)
    sys.exit(1)


def main():
    rate_hz = rospy.get_param("~rate", 1.0)
    port = rospy.get_param("~port", "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0")
    baud = int(rospy.get_param("~baud", 9600))

    pub_temp = rospy.Publisher("/sensors/sht40/temperature", Float64, queue_size=1)
    pub_hum = rospy.Publisher("/sensors/sht40/humidity", Float64, queue_size=1)

    sensor = SHT40Sensor(port=port, baud=baud)
    rate = rospy.Rate(rate_hz)
    rospy.loginfo("SHT40 node (Arduino serial) publishing at %.1f Hz on %s", rate_hz, port)

    try:
        while not rospy.is_shutdown():
            temp, humidity, _ = sensor.read_data()
            if temp is not None:
                pub_temp.publish(Float64(data=float(temp)))
            if humidity is not None:
                pub_hum.publish(Float64(data=float(humidity)))
            rate.sleep()
    finally:
        sensor.close()


if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        pass
