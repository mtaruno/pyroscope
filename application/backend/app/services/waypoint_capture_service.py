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
from app.models.scan import ScanRecord
from app.config import settings
from app.services.ros_sensor_bridge import (
    is_ros_configured,
    start_ros_bridge,
    get_latest_from_ros,
    wait_for_next_capture_ready,
    clear_capture_ready_queue,
)


def _pyroscope_root() -> Path:
    # From app/services/waypoint_capture_service.py -> backend/app -> backend -> application
    return Path(__file__).resolve().parent.parent.parent.parent


_sht40_script = _pyroscope_root() / "sht40_reader.py"
_thermal_script = _pyroscope_root() / "thermal_capture.py"
FALLBACK_INTERVAL_SEC = 3

_capture_state = {
    "scan_id": None,
    "status": "idle",
    "captured_points": 0,
    "total_points": None,
    "last_capture_ready": False,
    "stop_event": None,
    "thread": None,
    "use_ros": False,
}
_capture_state_lock = threading.Lock()


def _run_sht40_once(port: str = None) -> dict:
    """Run sht40_reader.py --once (Arduino serial), return parsed JSON or empty dict."""
    if not _sht40_script.exists():
        return {"temperature": None, "humidity": None}
    cmd = [str(_sht40_script), "--once"]
    if port:
        cmd.extend(["--port", port])
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


def _mark_scan_completed(scan_id: int) -> None:
    db = SessionLocal()
    try:
        scan = db.query(ScanRecord).filter(ScanRecord.id == scan_id).first()
        if scan and scan.completed_at is None:
            scan.completed_at = datetime.utcnow()
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


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
        capture_ready = wait_for_next_capture_ready(timeout_sec=0.5) if use_ros else False
        if stop_event.is_set():
            break
        if use_ros:
            if not capture_ready:
                continue
            with _capture_state_lock:
                _capture_state["last_capture_ready"] = True
        else:
            # Keep legacy behavior when ROS command stream is unavailable.
            stop_event.wait(FALLBACK_INTERVAL_SEC)
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
            sht40_data = _run_sht40_once()
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

        with _capture_state_lock:
            _capture_state["captured_points"] = sequence_index + 1
            total_points = _capture_state["total_points"]
        sequence_index += 1
        if total_points and sequence_index >= total_points:
            with _capture_state_lock:
                _capture_state["status"] = "completed"
            _mark_scan_completed(scan_id)
            stop_event.set()
            break

    with _capture_state_lock:
        if _capture_state["status"] not in ("completed", "stopped"):
            _capture_state["status"] = "stopped"


def start_capture_loop(scan_id: int, total_points: Optional[int] = None) -> None:
    """Start background thread that captures on each ROS '/coverage/capture_ready'=true event."""
    if _capture_state["thread"] is not None and _capture_state["thread"].is_alive():
        return
    thermal_dir = os.path.join(settings.UPLOAD_DIR, "thermal_latest")
    rgb_dir = os.path.join(settings.UPLOAD_DIR, "realsense_latest")
    os.makedirs(thermal_dir, exist_ok=True)
    os.makedirs(rgb_dir, exist_ok=True)
    use_ros = is_ros_configured() and start_ros_bridge(thermal_dir, rgb_dir)
    clear_capture_ready_queue()
    _capture_state["use_ros"] = use_ros
    _capture_state["stop_event"] = threading.Event()
    with _capture_state_lock:
        _capture_state["scan_id"] = scan_id
        _capture_state["captured_points"] = 0
        _capture_state["total_points"] = total_points
        _capture_state["status"] = "running"
        _capture_state["last_capture_ready"] = False
    _capture_state["thread"] = threading.Thread(
        target=_capture_loop_impl,
        args=(scan_id,),
        daemon=True,
    )
    _capture_state["thread"].start()


def stop_capture_loop() -> Optional[int]:
    """Signal loop to stop and return current scan_id."""
    if _capture_state["stop_event"]:
        _capture_state["stop_event"].set()
    with _capture_state_lock:
        scan_id = _capture_state["scan_id"]
        _capture_state["scan_id"] = None
        _capture_state["stop_event"] = None
        _capture_state["status"] = "stopped"
    if _capture_state["thread"]:
        _capture_state["thread"].join(timeout=5)
        _capture_state["thread"] = None
    return scan_id


def get_current_scan_id() -> Optional[int]:
    with _capture_state_lock:
        return _capture_state.get("scan_id")


def get_capture_progress() -> dict:
    with _capture_state_lock:
        scan_id = _capture_state.get("scan_id")
        captured_points = int(_capture_state.get("captured_points") or 0)
        total_points = _capture_state.get("total_points")
        status = _capture_state.get("status") or "idle"
        last_capture_ready = _capture_state.get("last_capture_ready")
    progress_percent = 0.0
    if total_points and total_points > 0:
        progress_percent = min(100.0, (captured_points / total_points) * 100.0)
    return {
        "scan_id": scan_id,
        "captured_points": captured_points,
        "total_points": total_points,
        "progress_percent": progress_percent,
        "status": status,
        "last_capture_ready": bool(last_capture_ready),
    }
