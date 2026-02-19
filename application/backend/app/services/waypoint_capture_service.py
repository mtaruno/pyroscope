"""
Waypoint capture: every N seconds capture SHT40 + thermal + RealSense RGB,
store sample and images. Data source: ROS topics (when ROS_MASTER_URI is set) or subprocess fallback.
"""

import json
import os
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Optional
from datetime import datetime

from app.database import SessionLocal
from app.models.waypoint_sample import ScanWaypointSample
from app.models.image import ScanImage, ImageType
from app.config import settings
from app.services.ros_sensor_bridge import is_ros_configured, start_ros_bridge, get_latest_from_ros


def _pyroscope_root() -> Path:
    # From app/services/waypoint_capture_service.py -> backend/app -> backend -> application
    return Path(__file__).resolve().parent.parent.parent.parent


WAYPOINT_INTERVAL_SEC = 3
_sht40_script = _pyroscope_root() / "sht40_reader.py"
_thermal_script = _pyroscope_root() / "thermal_capture.py"

_capture_state = {
    "scan_id": None,
    "stop_event": None,
    "thread": None,
    "use_ros": False,
}


def _run_sht40_once(simulate: bool = False) -> dict:
    """Run sht40_reader.py --once, return parsed JSON or empty dict."""
    if not _sht40_script.exists():
        return {"temperature": None, "humidity": None}
    cmd = [str(_sht40_script), "--once"]
    if simulate:
        cmd.append("--simulate")
    try:
        out = subprocess.run(
            cmd,
            cwd=str(_pyroscope_root()),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            return json.loads(out.stdout.strip())
    except Exception:
        pass
    return {"temperature": None, "humidity": None}


def _run_thermal_once(image_path: str = None, simulate: bool = False) -> dict:
    """Run thermal_capture.py, return parsed JSON."""
    if not _thermal_script.exists():
        return {"thermal_mean": None, "image_path": None}
    cmd = [str(_thermal_script)]
    if image_path:
        cmd.extend(["--image", image_path])
    if simulate:
        cmd.append("--simulate")
    try:
        out = subprocess.run(
            cmd,
            cwd=str(_pyroscope_root()),
            capture_output=True,
            text=True,
            timeout=15,
        )
        if out.returncode == 0 and out.stdout.strip():
            return json.loads(out.stdout.strip())
    except Exception:
        pass
    return {"thermal_mean": None, "image_path": None}


def _capture_loop_impl(scan_id: int):
    stop_event = _capture_state["stop_event"]
    if not stop_event:
        return

    thermal_dir = os.path.join(settings.UPLOAD_DIR, "thermal_latest")
    rgb_dir = os.path.join(settings.UPLOAD_DIR, "visible", str(scan_id))
    os.makedirs(thermal_dir, exist_ok=True)
    os.makedirs(rgb_dir, exist_ok=True)

    thermal_image_path = os.path.join(thermal_dir, f"scan_{scan_id}.jpg")
    sequence_index = 0
    use_ros = _capture_state.get("use_ros", False)
    simulate = not use_ros and not _sht40_script.exists()

    while not stop_event.is_set():
        stop_event.wait(WAYPOINT_INTERVAL_SEC)
        if stop_event.is_set():
            break

        rgb_waypoint_path = os.path.join(rgb_dir, f"waypoint_{sequence_index:04d}.jpg")

        if use_ros:
            ros_data = get_latest_from_ros()
            sht40_data = {"temperature": ros_data.get("temperature"), "humidity": ros_data.get("humidity")}
            thermal_data = {"thermal_mean": ros_data.get("thermal_mean"), "image_path": None}

            # Copy latest thermal frame
            src_thermal = ros_data.get("thermal_image_path")
            if src_thermal and os.path.exists(src_thermal):
                try:
                    shutil.copy2(src_thermal, thermal_image_path)
                    thermal_data["image_path"] = thermal_image_path
                except Exception:
                    pass

            # Copy latest RGB frame for this waypoint
            src_rgb = ros_data.get("rgb_image_path")
            if src_rgb and os.path.exists(src_rgb):
                try:
                    shutil.copy2(src_rgb, rgb_waypoint_path)
                except Exception:
                    rgb_waypoint_path = None
            else:
                rgb_waypoint_path = None
        else:
            sht40_data = _run_sht40_once(simulate=simulate)
            thermal_data = _run_thermal_once(image_path=thermal_image_path, simulate=simulate)
            rgb_waypoint_path = None  # no RealSense in subprocess mode

        db = SessionLocal()
        try:
            now = datetime.utcnow()
            sample = ScanWaypointSample(
                scan_id=scan_id,
                sequence_index=sequence_index,
                captured_at=now,
                air_temperature=sht40_data.get("temperature"),
                air_humidity=sht40_data.get("humidity"),
                thermal_mean=thermal_data.get("thermal_mean"),
            )
            db.add(sample)

            # Upsert single "thermal_latest" ScanImage for this scan
            image_path = thermal_data.get("image_path")
            if image_path and os.path.exists(image_path):
                existing = db.query(ScanImage).filter(
                    ScanImage.scan_id == scan_id,
                    ScanImage.image_type == ImageType.thermal_latest,
                ).first()
                if existing:
                    existing.file_path = image_path
                    existing.captured_at = now
                else:
                    db.add(ScanImage(
                        scan_id=scan_id,
                        image_type=ImageType.thermal_latest,
                        file_path=image_path,
                        mime_type="image/jpeg",
                        captured_at=now,
                    ))

            # Save per-waypoint RealSense RGB image
            if rgb_waypoint_path and os.path.exists(rgb_waypoint_path):
                rgb_image = ScanImage(
                    scan_id=scan_id,
                    image_type=ImageType.visible,
                    file_path=rgb_waypoint_path,
                    mime_type="image/jpeg",
                    captured_at=now,
                    meta_data={"sequence_index": sequence_index},
                )
                db.add(rgb_image)
                db.flush()  # get rgb_image.id before linking
                sample.rgb_image_id = rgb_image.id

            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

        sequence_index += 1


def start_capture_loop(scan_id: int) -> None:
    """Start background thread that captures every WAYPOINT_INTERVAL_SEC (from ROS or subprocess)."""
    if _capture_state["thread"] is not None and _capture_state["thread"].is_alive():
        return
    thermal_dir = os.path.join(settings.UPLOAD_DIR, "thermal_latest")
    rgb_dir = os.path.join(settings.UPLOAD_DIR, "realsense_latest")
    os.makedirs(thermal_dir, exist_ok=True)
    os.makedirs(rgb_dir, exist_ok=True)
    use_ros = is_ros_configured() and start_ros_bridge(thermal_dir, rgb_dir)
    _capture_state["use_ros"] = use_ros
    _capture_state["stop_event"] = threading.Event()
    _capture_state["scan_id"] = scan_id
    _capture_state["thread"] = threading.Thread(
        target=_capture_loop_impl,
        args=(scan_id,),
        daemon=True,
    )
    _capture_state["thread"].start()


def stop_capture_loop() -> Optional[int]:
    """Signal loop to stop and return current scan_id."""
    _capture_state["stop_event"].set()
    scan_id = _capture_state["scan_id"]
    _capture_state["scan_id"] = None
    _capture_state["stop_event"] = None
    if _capture_state["thread"]:
        _capture_state["thread"].join(timeout=5)
        _capture_state["thread"] = None
    return scan_id


def get_current_scan_id() -> Optional[int]:
    return _capture_state.get("scan_id")
