from sqlalchemy import Column, Integer, DECIMAL, TIMESTAMP, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class ScanWaypointSample(Base):
    """One waypoint capture during a scan: SHT40 + thermal mean (no image per sample)."""
    __tablename__ = "scan_waypoint_samples"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    scan_id = Column(Integer, ForeignKey("scan_records.id", ondelete="CASCADE"), nullable=False)
    sequence_index = Column(Integer, nullable=False)
    captured_at = Column(TIMESTAMP, nullable=False)
    air_temperature = Column(DECIMAL(5, 2), nullable=True)
    air_humidity = Column(DECIMAL(5, 2), nullable=True)
    thermal_mean = Column(DECIMAL(5, 2), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    scan = relationship("ScanRecord", back_populates="waypoint_samples")

    __table_args__ = (
        Index("idx_waypoint_scan_seq", "scan_id", "sequence_index"),
    )
