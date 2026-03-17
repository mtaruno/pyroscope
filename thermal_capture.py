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


def colorize_thermal_celsius(frame_celsius):
    """Piecewise thermal mapping in Celsius."""
    if cv is None or np is None:
        return frame_celsius

    arr = np.array(frame_celsius, dtype=np.float32)
    t_blue = 13.0
    t_warm = 28.0
    t_red = 35.0

    r = np.zeros_like(arr, dtype=np.float32)
    g = np.zeros_like(arr, dtype=np.float32)
    b = np.zeros_like(arr, dtype=np.float32)

    cold_mask = arr <= t_blue
    b[cold_mask] = 255.0

    gentle_mask = (arr > t_blue) & (arr < t_warm)
    if np.any(gentle_mask):
        u = (arr[gentle_mask] - t_blue) / (t_warm - t_blue)
        u = np.clip(u, 0.0, 1.0)
        u = np.power(u, 2.4)
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
    return cv.cvtColor(rgb, cv.COLOR_RGB2BGR)

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
            # Use fixed Celsius mapping for saved thermal preview.
            frame_blur = cv.GaussianBlur(frame.astype(np.float32), (3, 3), 0)
            thermal_color = colorize_thermal_celsius(frame_blur)
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
