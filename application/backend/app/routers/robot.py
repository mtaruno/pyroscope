from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime
import time
from app.database import get_db
from app.models.robot import RobotStatus
from app.models.scan import ScanRecord
from app.schemas.robot import RobotStatusCreate, RobotStatusResponse
from app.schemas.response import RobotStatusResponse as RobotStatusCreateResponse
from app.utils.validators import validate_operating_state
from app.services.waypoint_capture_service import start_capture_loop, stop_capture_loop, get_capture_progress
from app.services.ros_sensor_bridge import is_ros_configured, start_ros_bridge, get_latest_from_ros
from app.config import settings
import subprocess
import os
import signal
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/robot", tags=["Robot Status"])

# Store active mission process
mission_process = None


def _ensure_ros_bridge_for_status() -> None:
    """Ensure ROS bridge is running so /voltage can be consumed for battery status."""
    if not is_ros_configured():
        return
    thermal_dir = os.path.join(settings.UPLOAD_DIR, "thermal_latest")
    rgb_dir = os.path.join(settings.UPLOAD_DIR, "realsense_latest")
    os.makedirs(thermal_dir, exist_ok=True)
    os.makedirs(rgb_dir, exist_ok=True)
    start_ros_bridge(thermal_dir, rgb_dir)


@router.post("/status", response_model=RobotStatusCreateResponse, status_code=status.HTTP_201_CREATED)
async def update_robot_status(
    status_data: RobotStatusCreate,
    db: Session = Depends(get_db)
):
    """Update robot status"""
    # Validate operating state
    if status_data.operating_state:
        status_data.operating_state = validate_operating_state(status_data.operating_state)

    robot_status = RobotStatus(
        robot_id=status_data.robot_id,
        battery_level=status_data.battery_level,
        storage_used=status_data.storage_used,
        storage_total=status_data.storage_total,
        signal_strength=status_data.signal_strength,
        operating_state=status_data.operating_state,
        latitude=status_data.latitude,
        longitude=status_data.longitude
    )

    db.add(robot_status)
    db.commit()
    db.refresh(robot_status)

    return RobotStatusCreateResponse(status_id=robot_status.id)


# Mission Config and Endpoints - MUST come before /{robot_id}/status route
class MissionConfig(BaseModel):
    area_size_m: float = 50.0
    sampling_precision_m: float = 5.0
    area_width: Optional[float] = None
    area_height: Optional[float] = None
    row_spacing: float = 0.5
    waypoint_spacing: float = 0.5
    origin_x: float = 0.0
    origin_y: float = 0.0
    dwell_time: float = 2.0
    waypoint_timeout: float = 30.0


def _calc_total_waypoints(area_width: float, area_height: float,
                          row_spacing: float, waypoint_spacing: float,
                          wall_margin: float = 0.30) -> int:
    """Match the coverage_planner.py waypoint generation logic (centered grid)."""
    import math
    ew = area_width - 2 * wall_margin  # centered: same effective width
    eh = area_height - 2 * wall_margin
    if ew <= 0 or eh <= 0:
        return 1  # center-point-only fallback
    num_rows = max(1, int(math.ceil(eh / row_spacing)) + 1)
    num_cols = max(1, int(math.ceil(ew / waypoint_spacing)) + 1)
    return num_rows * num_cols


@router.post("/mission/start")
async def start_coverage_mission(config: MissionConfig = None, db: Session = Depends(get_db)):
    """Start the lawnmower coverage mission and waypoint capture loop."""
    global mission_process

    if mission_process is not None and mission_process.poll() is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mission already running"
        )

    try:
        config = config or MissionConfig()
        area_size_m = float(config.area_size_m)
        area_width = float(config.area_width) if config.area_width is not None else area_size_m
        area_height = float(config.area_height) if config.area_height is not None else area_size_m
        total_points = _calc_total_waypoints(
            area_width, area_height,
            config.row_spacing, config.waypoint_spacing,
        )

        # Create scan record (in progress) so we have scan_id for waypoint samples
        scan = ScanRecord(
            zone_id="A-01",
            latitude=34.2257,
            longitude=-117.8512,
            scan_area=f"{int(area_size_m)} m × {int(area_size_m)} m",
            completed_at=None,
        )
        db.add(scan)
        db.commit()
        db.refresh(scan)
        scan_id = scan.id

        # Build a clean env that removes the Python 3.9 venv but
        # keeps the normal system environment intact for ROS
        clean_env = {
            k: v for k, v in os.environ.items()
            if k not in ('VIRTUAL_ENV', 'PYTHONHOME', 'PYTHONPATH', 'CONDA_DEFAULT_ENV')
        }
        # Remove venv bin directory from PATH
        clean_env['PATH'] = ':'.join(
            p for p in clean_env.get('PATH', '').split(':')
            if 'venv' not in p
        )

        ros_cmd = (
            f'source /opt/ros/melodic/setup.bash && '
            f'source ~/pyroscope/catkin_ws/devel/setup.bash && '
            f'/opt/ros/melodic/bin/roslaunch pyroscope_navigation coverage_mission_nav.launch '
            f'area_width:={area_width} '
            f'area_height:={area_height} '
            f'row_spacing:={config.row_spacing} '
            f'waypoint_spacing:={config.waypoint_spacing} '
            f'origin_x:={config.origin_x} '
            f'origin_y:={config.origin_y} '
            f'dwell_time:={config.dwell_time} '
            f'waypoint_timeout:={config.waypoint_timeout}'
        )
        cmd = ['bash', '-c', ros_cmd]

        mission_process = subprocess.Popen(
            cmd,
            env=clean_env,
            preexec_fn=os.setsid if hasattr(os, "setsid") else None,
        )
        time.sleep(1.0)
        if mission_process.poll() is not None:
            raise RuntimeError(f"roslaunch exited immediately with return code {mission_process.returncode}")

        # Start waypoint capture loop (one sample per '/coverage/capture_ready'=true message).
        start_capture_loop(scan_id, total_points=total_points, require_ros=True)
        progress = get_capture_progress()

        return {
            "status": "started",
            "message": "Coverage mission started successfully",
            "scan_id": scan_id,
            "pid": mission_process.pid if mission_process else None,
            "config": config.dict(),
            "captured_points": progress["captured_points"],
            "total_points": progress["total_points"],
            "progress_percent": progress["progress_percent"],
        }

    except Exception as e:
        if mission_process is not None and mission_process.poll() is None:
            try:
                pgid = os.getpgid(mission_process.pid)
                if pgid != os.getpgrp():
                    os.killpg(pgid, signal.SIGTERM)
                else:
                    mission_process.terminate()
                mission_process.wait(timeout=5)
            except Exception:
                pass
            mission_process = None  # noqa: PLW0602
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start mission: {str(e)}"
        )


@router.post("/mission/stop")
async def stop_coverage_mission(db: Session = Depends(get_db)):
    """Stop the running coverage mission and waypoint capture; mark scan completed."""
    global mission_process

    # Stop waypoint capture loop and get scan_id to complete
    stopped_scan_id = stop_capture_loop()

    if mission_process is not None and mission_process.poll() is None:
        try:
            pgid = os.getpgid(mission_process.pid)
            # Only kill the child process group, never our own
            if pgid != os.getpgrp():
                os.killpg(pgid, signal.SIGTERM)
            else:
                mission_process.terminate()
            mission_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                pgid = os.getpgid(mission_process.pid)
                if pgid != os.getpgrp():
                    os.killpg(pgid, signal.SIGKILL)
                else:
                    mission_process.kill()
            except Exception:
                pass
        except Exception:
            pass
        mission_process = None  # noqa: PLW0602

    if stopped_scan_id:
        scan = db.query(ScanRecord).filter(ScanRecord.id == stopped_scan_id).first()
        if scan and scan.completed_at is None:
            scan.completed_at = datetime.utcnow()
            db.commit()
    progress = get_capture_progress()

    return {
        "status": "stopped",
        "message": "Coverage mission stopped successfully",
        "scan_id": stopped_scan_id,
        "captured_points": progress["captured_points"],
        "total_points": progress["total_points"],
        "progress_percent": progress["progress_percent"],
    }


@router.get("/mission/status")
async def get_mission_status():
    """Get the current status of the coverage mission"""
    global mission_process

    progress = get_capture_progress()
    active_scan_id = progress.get("scan_id")

    if mission_process is None and not active_scan_id:
        return {
            "status": "idle",
            "running": False,
            "captured_points": progress["captured_points"],
            "total_points": progress["total_points"],
            "progress_percent": progress["progress_percent"],
            "message": "No mission has been started",
        }

    if active_scan_id and progress.get("status") == "completed":
        return {
            "status": "completed",
            "running": False,
            "pid": mission_process.pid if mission_process and mission_process.poll() is None else None,
            "scan_id": active_scan_id,
            "captured_points": progress["captured_points"],
            "total_points": progress["total_points"],
            "progress_percent": progress["progress_percent"],
            "message": "Mission completed",
        }

    if active_scan_id and progress.get("status") == "running":
        return {
            "status": "running",
            "running": True,
            "pid": mission_process.pid if mission_process else None,
            "scan_id": active_scan_id,
            "captured_points": progress["captured_points"],
            "total_points": progress["total_points"],
            "progress_percent": progress["progress_percent"],
            "message": "Mission is currently running",
        }

    if mission_process is not None and mission_process.poll() is None:
        return {
            "status": "running",
            "running": True,
            "pid": mission_process.pid,
            "scan_id": active_scan_id,
            "captured_points": progress["captured_points"],
            "total_points": progress["total_points"],
            "progress_percent": progress["progress_percent"],
            "message": "Mission is currently running",
        }
    else:
        return_code = mission_process.returncode if mission_process else 0
        mission_process = None
        return {
            "status": "completed" if return_code == 0 else "failed",
            "running": False,
            "scan_id": active_scan_id,
            "captured_points": progress["captured_points"],
            "total_points": progress["total_points"],
            "progress_percent": progress["progress_percent"],
            "return_code": return_code,
            "message": f"Mission completed with return code {return_code}",
        }


@router.get("/mission/progress")
async def get_mission_progress():
    progress = get_capture_progress()
    running = progress.get("status") == "running"
    return {
        "running": running,
        **progress,
    }


# Robot Status Endpoint - MUST come AFTER mission endpoints to avoid route conflicts
@router.get("/{robot_id}/status", response_model=RobotStatusResponse)
async def get_robot_status(robot_id: str, db: Session = Depends(get_db)):
    """Get latest robot status"""
    _ensure_ros_bridge_for_status()
    ros_data = get_latest_from_ros()
    ros_battery = ros_data.get("battery_percent")

    robot_status = (
        db.query(RobotStatus)
        .filter(RobotStatus.robot_id == robot_id)
        .order_by(desc(RobotStatus.recorded_at))
        .first()
    )

    if not robot_status:
        if ros_battery is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Robot status not found"
            )
        return RobotStatusResponse(
            robot_id=robot_id,
            battery_level=int(ros_battery),
            storage_used=None,
            storage_total=None,
            signal_strength="Good",
            operating_state="idle",
            latitude=None,
            longitude=None,
            recorded_at=datetime.utcnow(),
        )

    return RobotStatusResponse(
        robot_id=robot_status.robot_id,
        battery_level=int(ros_battery) if ros_battery is not None else robot_status.battery_level,
        storage_used=float(robot_status.storage_used) if robot_status.storage_used else None,
        storage_total=float(robot_status.storage_total) if robot_status.storage_total else None,
        signal_strength=robot_status.signal_strength,
        operating_state=robot_status.operating_state,
        latitude=float(robot_status.latitude) if robot_status.latitude else None,
        longitude=float(robot_status.longitude) if robot_status.longitude else None,
        recorded_at=robot_status.recorded_at
    )
