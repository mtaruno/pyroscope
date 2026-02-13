from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database import get_db
from app.models.robot import RobotStatus
from app.schemas.robot import RobotStatusCreate, RobotStatusResponse
from app.schemas.response import RobotStatusResponse as RobotStatusCreateResponse
from app.utils.validators import validate_operating_state

router = APIRouter(prefix="/robot", tags=["Robot Status"])


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


@router.get("/{robot_id}/status", response_model=RobotStatusResponse)
async def get_robot_status(robot_id: str, db: Session = Depends(get_db)):
    """Get latest robot status"""
    status = (
        db.query(RobotStatus)
        .filter(RobotStatus.robot_id == robot_id)
        .order_by(desc(RobotStatus.recorded_at))
        .first()
    )
    
    if not status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Robot status not found"
        )
    
    return RobotStatusResponse(
        robot_id=status.robot_id,
        battery_level=status.battery_level,
        storage_used=float(status.storage_used) if status.storage_used else None,
        storage_total=float(status.storage_total) if status.storage_total else None,
        signal_strength=status.signal_strength,
        operating_state=status.operating_state,
        latitude=float(status.latitude) if status.latitude else None,
        longitude=float(status.longitude) if status.longitude else None,
        recorded_at=status.recorded_at
    )
