from sqlalchemy import Column, Integer, String, DECIMAL, TIMESTAMP, Enum, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class RiskLevel(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class ScanRecord(Base):
    __tablename__ = "scan_records"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    zone_id = Column(String(50), nullable=False)
    latitude = Column(DECIMAL(10, 8), nullable=False)
    longitude = Column(DECIMAL(11, 8), nullable=False)
    gps_accuracy = Column(DECIMAL(5, 2), nullable=True)
    scan_area = Column(String(50), nullable=True)  # "50 m × 50 m"
    duration = Column(String(50), nullable=True)  # "15 min 32 sec"
    risk_level = Column(Enum(RiskLevel), nullable=True)
    avg_plant_temp = Column(DECIMAL(5, 2), nullable=True)
    avg_air_temp = Column(DECIMAL(5, 2), nullable=True)
    avg_humidity = Column(DECIMAL(5, 2), nullable=True)
    wind_speed = Column(DECIMAL(5, 2), nullable=True)
    temp_diff = Column(DECIMAL(5, 2), nullable=True)
    fuel_load = Column(String(20), nullable=True)
    one_hour_fuel = Column(DECIMAL(10, 4), nullable=True)
    ten_hour_fuel = Column(DECIMAL(10, 4), nullable=True)
    hundred_hour_fuel = Column(DECIMAL(10, 4), nullable=True)
    pine_cone_count = Column(Integer, nullable=True)
    fuel_density = Column(DECIMAL(5, 2), nullable=True)
    biomass = Column(DECIMAL(5, 2), nullable=True)
    robot_id = Column(String(50), nullable=True)
    completed_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # Relationships
    environmental_data = relationship("EnvironmentalData", back_populates="scan", cascade="all, delete-orphan")
    images = relationship("ScanImage", back_populates="scan", cascade="all, delete-orphan")
    waypoint_samples = relationship("ScanWaypointSample", back_populates="scan", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_location', 'latitude', 'longitude'),
        Index('idx_completed_at', 'completed_at'),
        Index('idx_risk_level', 'risk_level'),
    )
