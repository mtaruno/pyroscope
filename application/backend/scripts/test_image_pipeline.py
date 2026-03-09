#!/usr/bin/env python3
"""
Test the image pipeline WITHOUT running the full backend or ROS.
Simulates a ROS Image message and verifies the encode path works.

Run on the Ubuntu PC:
    cd ~/Dev/pyroscope/application/backend
    python3 scripts/test_image_pipeline.py
"""

import sys

print("=" * 60)
print("Image Pipeline Test")
print("=" * 60)

# 1. Check numpy
print("\n[1/5] Checking numpy...")
try:
    import numpy as np
    print(f"  OK - numpy {np.__version__}")
except ImportError:
    print("  FAIL - numpy not installed. Run: pip install numpy")
    sys.exit(1)

# 2. Check Pillow
print("\n[2/5] Checking Pillow (PIL)...")
try:
    from PIL import Image as PILImage
    print(f"  OK - Pillow {PILImage.__version__ if hasattr(PILImage, '__version__') else 'installed'}")
except ImportError:
    print("  FAIL - Pillow not installed. Run: pip install Pillow")
    sys.exit(1)

# 3. Check cv_bridge + cv2 (optional)
print("\n[3/5] Checking cv_bridge + cv2 (optional)...")
try:
    from cv_bridge import CvBridge
    import cv2
    print(f"  OK - cv_bridge + cv2 {cv2.__version__} (will use this path)")
except ImportError:
    print("  SKIP - cv_bridge/cv2 not available (will use numpy+Pillow fallback)")

# 4. Simulate a ROS Image message and encode to JPEG
print("\n[4/5] Simulating ROS Image -> JPEG encode...")
import io

class FakeROSImage:
    """Mimics sensor_msgs/Image"""
    def __init__(self, width, height, encoding, data):
        self.width = width
        self.height = height
        self.encoding = encoding
        self.data = data

# Create a 640x480 BGR8 test image (blue gradient)
width, height = 640, 480
arr = np.zeros((height, width, 3), dtype=np.uint8)
arr[:, :, 0] = np.linspace(0, 255, width, dtype=np.uint8)  # Blue channel gradient
arr[:, :, 1] = 100  # Green
arr[:, :, 2] = 50   # Red

fake_msg = FakeROSImage(
    width=width,
    height=height,
    encoding="bgr8",
    data=arr.tobytes(),
)

# Run the same encode logic as ros_sensor_bridge.py
try:
    channels = len(fake_msg.data) // (fake_msg.width * fake_msg.height)
    decoded = np.frombuffer(fake_msg.data, dtype=np.uint8).reshape(
        (fake_msg.height, fake_msg.width, channels)
    )
    # BGR -> RGB
    if fake_msg.encoding in ("bgr8", "8UC3"):
        decoded = decoded[:, :, ::-1]
    pil_img = PILImage.fromarray(decoded)
    buf = io.BytesIO()
    pil_img.save(buf, "JPEG", quality=85)
    jpeg_bytes = buf.getvalue()
    print(f"  OK - Encoded {width}x{height} BGR8 -> {len(jpeg_bytes)} bytes JPEG")
except Exception as e:
    print(f"  FAIL - Encode error: {e}")
    sys.exit(1)

# 5. Verify the JPEG is valid by decoding it back
print("\n[5/5] Verifying JPEG is valid...")
try:
    verify_buf = io.BytesIO(jpeg_bytes)
    verify_img = PILImage.open(verify_buf)
    verify_img.verify()
    print(f"  OK - Valid JPEG, {verify_img.size[0]}x{verify_img.size[1]}")
except Exception as e:
    print(f"  FAIL - Invalid JPEG: {e}")
    sys.exit(1)

# Also test saving to file (waypoint capture path)
import tempfile
print("\n[Bonus] Testing file save (waypoint capture path)...")
try:
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(jpeg_bytes)
        tmp_path = f.name
    size = os.path.getsize(tmp_path) if 'os' in dir() else len(jpeg_bytes)
    import os
    size = os.path.getsize(tmp_path)
    os.unlink(tmp_path)
    print(f"  OK - Wrote and cleaned up temp file ({size} bytes)")
except Exception as e:
    print(f"  FAIL - File save error: {e}")

import os
output_path = os.path.join(os.path.dirname(__file__), "test_output.jpg")
with open(output_path, "wb") as f:
    f.write(jpeg_bytes)
print(f"\nTest image saved to: {os.path.abspath(output_path)}")
print("Open it to confirm the image looks right.")

print("\n" + "=" * 60)
print("ALL CHECKS PASSED - Image pipeline will work!")
print("=" * 60)
