#!/usr/bin/env python3
"""
Single-frame thermal capture for backend integration.
Opens MI48, reads one frame, computes mean temperature, optionally saves image.
Outputs JSON to stdout: {"thermal_mean": float, "image_path": str or null}
"""

import argparse
import json
import os
import sys

try:
    import numpy as np
except ImportError:
    np = None

try:
    import cv2 as cv
except ImportError:
    cv = None

# Optional: senxor MI48
try:
    from senxor.utils import data_to_frame, connect_senxor
    HAS_SENXOR = True
except ImportError:
    HAS_SENXOR = False

# Thermal display tuning (hypothesis 1):
# assume input frame is 0..255-like and larger value means hotter.
#   <= THERMAL_BLUE_CUTOFF_RAW -> fixed blue (background)
#   >= THERMAL_RED_AT_RAW      -> red
#   between cutoff..red_at     -> exponential rise
THERMAL_BLUE_CUTOFF_RAW = 170.0
THERMAL_RED_AT_RAW = 200.0
THERMAL_EXPONENT = 1.6


def colorize_thermal_raw(frame_raw):
    """Map raw-like thermal frame to pseudo-color using fixed thresholds."""
    if cv is None or np is None:
        return frame_raw

    if THERMAL_RED_AT_RAW <= THERMAL_BLUE_CUTOFF_RAW:
        raise ValueError("THERMAL_RED_AT_RAW must be greater than THERMAL_BLUE_CUTOFF_RAW")

    raw = np.array(frame_raw, dtype=np.float32)
    norm = np.zeros_like(raw, dtype=np.float32)
    hot_mask = raw > THERMAL_BLUE_CUTOFF_RAW
    if np.any(hot_mask):
        linear = (raw[hot_mask] - THERMAL_BLUE_CUTOFF_RAW) / (THERMAL_RED_AT_RAW - THERMAL_BLUE_CUTOFF_RAW)
        linear = np.clip(linear, 0.0, 1.0)
        norm[hot_mask] = np.power(linear, THERMAL_EXPONENT)
    # <= cutoff remains blue, >= red_at saturates to red
    norm = np.clip(norm, 0.0, 1.0)
    gray_uint8 = (norm * 255.0).astype(np.uint8)
    return cv.applyColorMap(gray_uint8, cv.COLORMAP_JET)


def capture_once(save_image_path=None, simulate=False):
    """
    Capture one thermal frame, compute mean, optionally save image.
    Returns dict with thermal_mean and image_path (if saved).
    """
    if simulate or not HAS_SENXOR:
        # Simulation: random mean, no image
        if np is None:
            thermal_mean = 28.0
        else:
            thermal_mean = float(np.random.uniform(25.0, 35.0))
        return {"thermal_mean": round(thermal_mean, 2), "image_path": None}

    mi48, _connected_port, _port_names = connect_senxor()
    mi48.set_fps(15)
    mi48.disable_filter(f1=True, f2=True, f3=True)
    mi48.set_filter_1(85)
    mi48.enable_filter(f1=True, f2=False, f3=False, f3_ks_5=False)
    mi48.set_offset_corr(0.0)
    mi48.set_sens_factor(100)
    mi48.start(stream=True, with_header=True)

    try:
        data, _header = mi48.read()
        if data is None:
            mi48.stop()
            return {"thermal_mean": None, "image_path": None, "error": "No frame"}

        frame = data_to_frame(data, (80, 62), hflip=False)
        thermal_mean = float(np.mean(frame))

        image_path = None
        if save_image_path and cv is not None:
            # Keep mild denoise in raw domain, but DO NOT use frame-by-frame remap().
            frame_blur = cv.GaussianBlur(frame.astype(np.float32), (3, 3), 0)
            thermal_color = colorize_thermal_raw(frame_blur)
            cv.imwrite(save_image_path, thermal_color)
            image_path = save_image_path
    finally:
        mi48.stop()

    return {
        "thermal_mean": round(thermal_mean, 2),
        "image_path": image_path,
    }


def main():
    parser = argparse.ArgumentParser(description="Single-frame thermal capture")
    parser.add_argument("--image", type=str, default=None, help="Path to save thermal image (optional)")
    parser.add_argument("--simulate", action="store_true", help="Simulate capture when hardware unavailable")
    args = parser.parse_args()

    try:
        result = capture_once(save_image_path=args.image, simulate=args.simulate)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"thermal_mean": None, "image_path": None, "error": str(e)}, default=str))
        sys.exit(1)


if __name__ == "__main__":
    main()
