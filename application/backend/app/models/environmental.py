from sqlalchemy import Column, Integer, DECIMAL, TIMESTAMP, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class EnvironmentalData(Base):
    __tablename__ = "environmental_data"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    scan_id = Column(Integer, ForeignKey("scan_records.id", ondelete="CASCADE"), nullable=False)
    air_temperature = Column(DECIMAL(5, 2), nullable=True)
    air_humidity = Column(DECIMAL(5, 2), nullable=True)
    wind_speed = Column(DECIMAL(5, 2), nullable=True)
    plant_temperature = Column(DECIMAL(5, 2), nullable=True)
    latitude = Column(DECIMAL(10, 8), nullable=True)
    longitude = Column(DECIMAL(11, 8), nullable=True)
    measured_at = Column(TIMESTAMP, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    # Fuel estimation fields for each point
    one_hour_fuel = Column(DECIMAL(10, 4), nullable=True)
    ten_hour_fuel = Column(DECIMAL(10, 4), nullable=True)
    hundred_hour_fuel = Column(DECIMAL(10, 4), nullable=True)
    
    # Relationships
    scan = relationship("ScanRecord", back_populates="environmental_data")
    
    __table_args__ = (
        Index('idx_scan_measured', 'scan_id', 'measured_at'),
    )
