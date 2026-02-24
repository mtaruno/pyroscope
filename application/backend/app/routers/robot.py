from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime
from app.database import get_db
from app.models.robot import RobotStatus
from app.models.scan import ScanRecord
from app.schemas.robot import RobotStatusCreate, RobotStatusResponse
from app.schemas.response import RobotStatusResponse as RobotStatusCreateResponse
from app.utils.validators import validate_operating_state
from app.services.waypoint_capture_service import start_capture_loop, stop_capture_loop
import subprocess
import os
import signal
from pydantic import BaseModel

router = APIRouter(prefix="/robot", tags=["Robot Status"])

# Store active mission process
mission_process = None


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
    area_width: float = 5.0
    area_height: float = 5.0
    row_spacing: float = 0.8
    waypoint_spacing: float = 0.5
    origin_x: float = 0.0
    origin_y: float = 0.0
    dwell_time: float = 2.0
    waypoint_timeout: float = 30.0


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
        # Create scan record (in progress) so we have scan_id for waypoint samples
        scan = ScanRecord(
            zone_id="A-01",
            latitude=34.2257,
            longitude=-117.8512,
            scan_area="50 m × 50 m",
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
            f'area_width:={config.area_width if config else 5.0} '
            f'area_height:={config.area_height if config else 5.0} '
            f'row_spacing:={config.row_spacing if config else 0.8} '
            f'waypoint_spacing:={config.waypoint_spacing if config else 0.5} '
            f'origin_x:={config.origin_x if config else 0.0} '
            f'origin_y:={config.origin_y if config else 0.0} '
            f'dwell_time:={config.dwell_time if config else 2.0} '
            f'waypoint_timeout:={config.waypoint_timeout if config else 30.0}'
        )
        cmd = ['bash', '-c', ros_cmd]

        # Start the mission as a background process (may fail on non-ROS hosts; continue for capture)
        try:
            mission_process = subprocess.Popen(
                cmd,
                env=clean_env,
                preexec_fn=os.setsid if hasattr(os, "setsid") else None,
            )
        except Exception:
            mission_process = None  # noqa: PLW0602

        # Start waypoint capture loop (3s interval: SHT40 + thermal, store samples)
        start_capture_loop(scan_id)

        return {
            "status": "started",
            "message": "Coverage mission started successfully",
            "scan_id": scan_id,
            "pid": mission_process.pid if mission_process else None,
            "config": config.dict() if config else {}
        }

    except Exception as e:
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
            os.killpg(os.getpgid(mission_process.pid), signal.SIGTERM)
            mission_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(mission_process.pid), signal.SIGKILL)
        except Exception:
            pass
        mission_process = None  # noqa: PLW0602

    if stopped_scan_id:
        scan = db.query(ScanRecord).filter(ScanRecord.id == stopped_scan_id).first()
        if scan and scan.completed_at is None:
            scan.completed_at = datetime.utcnow()
            db.commit()

    return {
        "status": "stopped",
        "message": "Coverage mission stopped successfully",
        "scan_id": stopped_scan_id,
    }


@router.get("/mission/status")
async def get_mission_status():
    """Get the current status of the coverage mission"""
    global mission_process

    if mission_process is None:
        return {
            "status": "idle",
            "running": False,
            "message": "No mission has been started"
        }

    if mission_process.poll() is None:
        return {
            "status": "running",
            "running": True,
            "pid": mission_process.pid,
            "message": "Mission is currently running"
        }
    else:
        return_code = mission_process.returncode
        mission_process = None
        return {
            "status": "completed" if return_code == 0 else "failed",
            "running": False,
            "return_code": return_code,
            "message": f"Mission completed with return code {return_code}"
        }


# Robot Status Endpoint - MUST come AFTER mission endpoints to avoid route conflicts
@router.get("/{robot_id}/status", response_model=RobotStatusResponse)
async def get_robot_status(robot_id: str, db: Session = Depends(get_db)):
    """Get latest robot status"""
    robot_status = (
        db.query(RobotStatus)
        .filter(RobotStatus.robot_id == robot_id)
        .order_by(desc(RobotStatus.recorded_at))
        .first()
    )

    if not robot_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Robot status not found"
        )

    return RobotStatusResponse(
        robot_id=robot_status.robot_id,
        battery_level=robot_status.battery_level,
        storage_used=float(robot_status.storage_used) if robot_status.storage_used else None,
        storage_total=float(robot_status.storage_total) if robot_status.storage_total else None,
        signal_strength=robot_status.signal_strength,
        operating_state=robot_status.operating_state,
        latitude=float(robot_status.latitude) if robot_status.latitude else None,
        longitude=float(robot_status.longitude) if robot_status.longitude else None,
        recorded_at=robot_status.recorded_at
    )
