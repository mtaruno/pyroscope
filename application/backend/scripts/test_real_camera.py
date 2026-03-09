#!/usr/bin/env python3
"""
Grab ONE real frame from /camera/color/image_raw via ROS and save as JPEG.

Run on the Ubuntu PC (where roscore is running):
    cd ~/Dev/pyroscope/application/backend
    python3 scripts/test_real_camera.py

Then copy the output to your Mac to view:
    scp <ubuntu_user>@10.0.0.46:~/Dev/pyroscope/application/backend/scripts/real_camera_test.jpg .
    open real_camera_test.jpg
"""

import sys
import os
import io

# Set ROS_MASTER_URI if not already set
if not os.environ.get("ROS_MASTER_URI"):
    os.environ["ROS_MASTER_URI"] = "http://10.0.0.46:11311"
if not os.environ.get("ROS_IP"):
    os.environ["ROS_IP"] = "10.0.0.46"

print("Checking dependencies...")
try:
    import numpy as np
    from PIL import Image as PILImage
    print(f"  numpy {np.__version__}, Pillow OK")
except ImportError as e:
    print(f"  FAIL: {e}")
    print("  Run: pip install numpy Pillow")
    sys.exit(1)

print("Importing rospy...")
try:
    import rospy
    from sensor_msgs.msg import Image
    print("  rospy OK")
except ImportError as e:
    print(f"  FAIL: {e}")
    print("  This script must run on the Ubuntu PC with ROS installed")
    sys.exit(1)

print(f"Connecting to ROS master at {os.environ['ROS_MASTER_URI']}...")
rospy.init_node("camera_test", anonymous=True, disable_signals=True)

print("Waiting for one frame from /camera/color/image_raw (timeout 10s)...")
try:
    msg = rospy.wait_for_message("/camera/color/image_raw", Image, timeout=10.0)
    print(f"  Got frame: {msg.width}x{msg.height}, encoding={msg.encoding}, {len(msg.data)} bytes")
except rospy.ROSException:
    print("  TIMEOUT - No message received in 10 seconds.")
    print("  Check: is sensors.launch running on the Jetson?")
    print("  Check: rostopic hz /camera/color/image_raw")
    sys.exit(1)

print("Encoding to JPEG (numpy+Pillow)...")
try:
    channels = len(msg.data) // (msg.width * msg.height) if msg.width and msg.height else 3
    arr = np.frombuffer(msg.data, dtype=np.uint8).reshape((msg.height, msg.width, channels))
    if msg.encoding in ("bgr8", "8UC3"):
        arr = arr[:, :, ::-1]  # BGR -> RGB
    pil_img = PILImage.fromarray(arr)
    buf = io.BytesIO()
    pil_img.save(buf, "JPEG", quality=85)
    jpeg_bytes = buf.getvalue()
    print(f"  OK - {len(jpeg_bytes)} bytes JPEG")
except Exception as e:
    print(f"  FAIL: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "real_camera_test.jpg")
with open(output_path, "wb") as f:
    f.write(jpeg_bytes)

print(f"\nSaved to: {output_path}")
print(f"Copy to Mac:  scp $USER@10.0.0.46:{output_path} ~/Desktop/ && open ~/Desktop/real_camera_test.jpg")
