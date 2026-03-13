"""
Waypoint capture: every N seconds capture SHT40 + thermal + RealSense RGB,
store sample and images. Data source: ROS topics (when ROS_MASTER_URI is set) or subprocess fallback.
"""

import json
import logging
import os
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

from app.database import SessionLocal
from app.models.waypoint_sample import ScanWaypointSample
from app.models.image import ScanImage, ImageType
from app.models.scan import ScanRecord
from app.config import settings
from app.services.ros_sensor_bridge import (
    is_ros_configured,
    start_ros_bridge,
    get_latest_from_ros,
    get_coverage_state,
    wait_for_next_capture_ready,
    clear_capture_ready_queue,
    clear_coverage_state,
    save_live_rgb_to_file,
    save_live_thermal_to_file,
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


def _sync_total_points_from_ros() -> Optional[int]:
    metrics = get_coverage_state()
    total_points = metrics.get("total_points")
    if total_points is not None:
        with _capture_state_lock:
            _capture_state["total_points"] = int(total_points)
    return total_points


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
        if use_ros:
            total_points = _sync_total_points_from_ros()
            coverage_state = get_coverage_state()
            with _capture_state_lock:
                captured_points = int(_capture_state.get("captured_points") or 0)
            if coverage_state.get("complete") and total_points is not None and captured_points >= int(total_points):
                with _capture_state_lock:
                    _capture_state["status"] = "completed"
                _mark_scan_completed(scan_id)
                stop_event.set()
                break

        capture_ready = wait_for_next_capture_ready(timeout_sec=0.5) if use_ros else False
        if stop_event.is_set():
            break
        if use_ros:
            if not capture_ready:
                continue
            logger.warning("capture_ready trigger received for waypoint %d", sequence_index)
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

            # Save latest thermal frame from in-memory cache
            if save_live_thermal_to_file(thermal_image_path):
                thermal_data["image_path"] = thermal_image_path

            # Save latest RGB frame from in-memory cache
            if not save_live_rgb_to_file(rgb_waypoint_path):
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
            logger.warning("Waypoint %d saved: temp=%s, humidity=%s, thermal=%s, rgb=%s",
                           sequence_index,
                           sht40_data.get("temperature"),
                           sht40_data.get("humidity"),
                           thermal_data.get("thermal_mean"),
                           rgb_waypoint_path)
        except Exception as e:
            logger.error("Failed to save waypoint %d: %s", sequence_index, e, exc_info=True)
            db.rollback()
        finally:
            db.close()

        ros_total_points = _sync_total_points_from_ros() if use_ros else None
        with _capture_state_lock:
            _capture_state["captured_points"] = sequence_index + 1
            if ros_total_points is not None:
                _capture_state["total_points"] = int(ros_total_points)
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


def start_capture_loop(scan_id: int, total_points: Optional[int] = None, require_ros: bool = False) -> None:
    """Start background thread that captures on each ROS '/coverage/capture_ready'=true event."""
    old_thread = _capture_state["thread"]
    if old_thread is not None and old_thread.is_alive():
        logger.warning("Capture loop already running (scan_id=%s), stopping it first", _capture_state.get("scan_id"))
        stop_capture_loop()
    # Clean up any dead thread reference
    _capture_state["thread"] = None
    thermal_dir = os.path.join(settings.UPLOAD_DIR, "thermal_latest")
    rgb_dir = os.path.join(settings.UPLOAD_DIR, "realsense_latest")
    os.makedirs(thermal_dir, exist_ok=True)
    os.makedirs(rgb_dir, exist_ok=True)
    use_ros = start_ros_bridge(thermal_dir, rgb_dir)
    if require_ros and not use_ros:
        raise RuntimeError("ROS bridge unavailable; refusing to simulate mission captures")
    clear_capture_ready_queue()
    clear_coverage_state()
    logger.warning("Starting capture loop: scan_id=%d, total_points=%s, use_ros=%s", scan_id, total_points, use_ros)
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
        use_ros = bool(_capture_state.get("use_ros"))
    ros_total_points = get_coverage_state().get("total_points") if use_ros else None
    if ros_total_points is not None:
        total_points = int(ros_total_points)
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
