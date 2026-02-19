from sqlalchemy import Column, Integer, String, DECIMAL, TIMESTAMP, Enum, ForeignKey, Index, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class ImageType(str, enum.Enum):
    thermal = "thermal"
    thermal_latest = "thermal_latest"
    visible = "visible"
    panorama = "panorama"
    detail = "detail"


class ScanImage(Base):
    __tablename__ = "scan_images"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    scan_id = Column(Integer, ForeignKey("scan_records.id", ondelete="CASCADE"), nullable=False)
    image_type = Column(Enum(ImageType), nullable=False)
    file_path = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String(50), nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    latitude = Column(DECIMAL(10, 8), nullable=True)
    longitude = Column(DECIMAL(11, 8), nullable=True)
    captured_at = Column(TIMESTAMP, nullable=True)
    meta_data = Column(JSON, nullable=True)  # Store EXIF and other metadata
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # Relationships
    scan = relationship("ScanRecord", back_populates="images")
    
    __table_args__ = (
        Index('idx_scan_type', 'scan_id', 'image_type'),
    )
