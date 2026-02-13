from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class RobotStatusCreate(BaseModel):
    robot_id: str
    battery_level: Optional[int] = None
    storage_used: Optional[float] = None
    storage_total: Optional[float] = None
    signal_strength: Optional[str] = None
    operating_state: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class RobotStatusResponse(BaseModel):
    robot_id: str
    battery_level: Optional[int] = None
    storage_used: Optional[float] = None
    storage_total: Optional[float] = None
    signal_strength: Optional[str] = None
    operating_state: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    recorded_at: datetime
    
    class Config:
        from_attributes = True
