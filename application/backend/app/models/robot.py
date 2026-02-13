from sqlalchemy import Column, Integer, String, DECIMAL, TIMESTAMP, Enum, Index
from sqlalchemy.sql import func
from app.database import Base
import enum


class OperatingState(str, enum.Enum):
    idle = "idle"
    scanning = "scanning"
    charging = "charging"
    error = "error"


class RobotStatus(Base):
    __tablename__ = "robot_status"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    robot_id = Column(String(50), nullable=False)
    battery_level = Column(Integer, nullable=True)
    storage_used = Column(DECIMAL(5, 2), nullable=True)
    storage_total = Column(DECIMAL(5, 2), nullable=True)
    signal_strength = Column(String(20), nullable=True)
    operating_state = Column(Enum(OperatingState), nullable=True)
    latitude = Column(DECIMAL(10, 8), nullable=True)
    longitude = Column(DECIMAL(11, 8), nullable=True)
    recorded_at = Column(TIMESTAMP, server_default=func.now())
    
    __table_args__ = (
        Index('idx_robot_time', 'robot_id', 'recorded_at'),
    )
