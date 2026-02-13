from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from app.models.scan import ScanRecord
from app.schemas.scan import ScanCreate


class ScanService:
    @staticmethod
    def create_scan(db: Session, scan_data: ScanCreate, user_id: int = None) -> ScanRecord:
        """Create a new scan record"""
        new_scan = ScanRecord(
            zone_id=scan_data.zone_id,
            latitude=scan_data.latitude,
            longitude=scan_data.longitude,
            gps_accuracy=scan_data.gps_accuracy,
            scan_area=scan_data.scan_area,
            duration=scan_data.duration,
            risk_level=scan_data.risk_level,
            avg_plant_temp=scan_data.avg_plant_temp,
            avg_air_temp=scan_data.avg_air_temp,
            avg_humidity=scan_data.avg_humidity,
            wind_speed=scan_data.wind_speed,
            temp_diff=scan_data.temp_diff,
            fuel_load=scan_data.fuel_load,
            fuel_density=scan_data.fuel_density,
            biomass=scan_data.biomass,
            robot_id=scan_data.robot_id,
            completed_at=scan_data.completed_at
        )
        
        db.add(new_scan)
        db.commit()
        db.refresh(new_scan)
        
        return new_scan
    
    @staticmethod
    def get_scans(
        db: Session,
        limit: int = 50,
        offset: int = 0,
        risk_level: Optional[str] = None,
        start_date: Optional[str] = None
    ) -> tuple[List[ScanRecord], int]:
        """Get list of scans with filters"""
        query = db.query(ScanRecord)
        
        # Apply filters
        if risk_level:
            query = query.filter(ScanRecord.risk_level == risk_level)
        
        if start_date:
            query = query.filter(ScanRecord.completed_at >= start_date)
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering
        scans = query.order_by(desc(ScanRecord.completed_at)).offset(offset).limit(limit).all()
        
        return scans, total
    
    @staticmethod
    def get_scan_by_id(db: Session, scan_id: int) -> Optional[ScanRecord]:
        """Get scan record by ID"""
        return db.query(ScanRecord).filter(ScanRecord.id == scan_id).first()
