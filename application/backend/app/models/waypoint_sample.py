from sqlalchemy import Column, Integer, DECIMAL, TIMESTAMP, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class ScanWaypointSample(Base):
    """One waypoint capture during a scan: SHT40 + thermal mean + optional RealSense RGB image."""
    __tablename__ = "scan_waypoint_samples"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    scan_id = Column(Integer, ForeignKey("scan_records.id", ondelete="CASCADE"), nullable=False)
    sequence_index = Column(Integer, nullable=False)
    captured_at = Column(TIMESTAMP, nullable=False)
    air_temperature = Column(DECIMAL(5, 2), nullable=True)
    air_humidity = Column(DECIMAL(5, 2), nullable=True)
    thermal_mean = Column(DECIMAL(5, 2), nullable=True)
    # FK to the RealSense RGB image captured at this waypoint (nullable: may not have camera)
    rgb_image_id = Column(Integer, ForeignKey("scan_images.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    scan = relationship("ScanRecord", back_populates="waypoint_samples")
    rgb_image = relationship("ScanImage", foreign_keys=[rgb_image_id])

    __table_args__ = (
        Index("idx_waypoint_scan_seq", "scan_id", "sequence_index"),
    )
