from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.schemas.scan import ScanCreate, ScanResponse, ScanListResponse, ScanListItem, ImageInfo
from app.schemas.response import ScanCreateResponse
from app.schemas.heatmap import HeatmapDataResponse, HeatmapPoint
from app.services.scan_service import ScanService
from app.services.fire_risk_service import FireRiskService
from app.utils.validators import validate_risk_level
from app.models.scan import ScanRecord
from app.models.environmental import EnvironmentalData

router = APIRouter(prefix="/scans", tags=["Scans"])


@router.post("", response_model=ScanCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_scan(
    scan_data: ScanCreate,
    db: Session = Depends(get_db)
):
    """Create a new scan record"""
    # Validate risk level
    if scan_data.risk_level:
        scan_data.risk_level = validate_risk_level(scan_data.risk_level)
    
    scan = ScanService.create_scan(db, scan_data, user_id=None)
    
    return ScanCreateResponse(scan_id=scan.id)


@router.get("", response_model=ScanListResponse)
async def get_scans(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    risk_level: Optional[str] = None,
    start_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get list of scans with pagination and filters"""
    # Validate risk level if provided
    if risk_level:
        risk_level = validate_risk_level(risk_level)
    
    scans, total = ScanService.get_scans(db, limit, offset, risk_level, start_date)
    
    scan_items = [
        ScanListItem(
            id=scan.id,
            zone_id=scan.zone_id,
            latitude=float(scan.latitude),
            longitude=float(scan.longitude),
            risk_level=scan.risk_level,
            completed_at=scan.completed_at,
            avg_air_temp=float(scan.avg_air_temp) if scan.avg_air_temp else None,
            avg_humidity=float(scan.avg_humidity) if scan.avg_humidity else None,
            avg_plant_temp=float(scan.avg_plant_temp) if scan.avg_plant_temp else None,  # ✅ 添加
            fuel_load=float(scan.fuel_load) if scan.fuel_load else None                   # ✅ 添加
        )
        for scan in scans
    ]
    
    return ScanListResponse(total=total, scans=scan_items)


@router.get("/{scan_id}", response_model=ScanResponse)
async def get_scan_detail(scan_id: int, db: Session = Depends(get_db)):
    """Get detailed information about a specific scan"""
    scan = ScanService.get_scan_by_id(db, scan_id)
    
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found"
        )
    
    # Convert images to ImageInfo objects
    image_infos = [
        ImageInfo(
            id=img.id,
            image_type=img.image_type,
            url=f"/api/images/{img.id}",
            captured_at=img.captured_at
        )
        for img in scan.images
    ]
    
    return ScanResponse(
        id=scan.id,
        zone_id=scan.zone_id,
        latitude=float(scan.latitude),
        longitude=float(scan.longitude),
        gps_accuracy=float(scan.gps_accuracy) if scan.gps_accuracy else None,
        scan_area=scan.scan_area,
        duration=scan.duration,
        risk_level=scan.risk_level,
        avg_plant_temp=float(scan.avg_plant_temp) if scan.avg_plant_temp else None,
        avg_air_temp=float(scan.avg_air_temp) if scan.avg_air_temp else None,
        avg_humidity=float(scan.avg_humidity) if scan.avg_humidity else None,
        wind_speed=float(scan.wind_speed) if scan.wind_speed else None,
        temp_diff=float(scan.temp_diff) if scan.temp_diff else None,
        fuel_load=scan.fuel_load,
        fuel_density=float(scan.fuel_density) if scan.fuel_density else None,
        biomass=float(scan.biomass) if scan.biomass else None,
        robot_id=scan.robot_id,
        completed_at=scan.completed_at,
        created_at=scan.created_at,
        images=image_infos
    )


@router.get("/{scan_id}/heatmap-data", response_model=HeatmapDataResponse)
async def get_heatmap_data(scan_id: int, db: Session = Depends(get_db)):
    """
    Get heatmap data for a scan
    Returns all environmental data points with calculated fire risk
    """
    # Verify scan exists
    scan = db.query(ScanRecord).filter(ScanRecord.id == scan_id).first()
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found"
        )
    
    # Get all environmental data points for this scan
    env_data = db.query(EnvironmentalData).filter(
        EnvironmentalData.scan_id == scan_id
    ).all()
    
    # Calculate fire risk for each point
    heatmap_points = []
    for point in env_data:
        # Calculate fire risk using the service
        fire_risk = FireRiskService.calculate_fire_risk(
            plant_temperature=float(point.plant_temperature) if point.plant_temperature else None,
            air_humidity=float(point.air_humidity) if point.air_humidity else None,
            one_hour_fuel=float(point.one_hour_fuel) if point.one_hour_fuel else None,
            ten_hour_fuel=float(point.ten_hour_fuel) if point.ten_hour_fuel else None,
            hundred_hour_fuel=float(point.hundred_hour_fuel) if point.hundred_hour_fuel else None
        )
        
        heatmap_point = HeatmapPoint(
            latitude=float(point.latitude) if point.latitude else 0,
            longitude=float(point.longitude) if point.longitude else 0,
            air_temperature=float(point.air_temperature) if point.air_temperature else None,
            air_humidity=float(point.air_humidity) if point.air_humidity else None,
            plant_temperature=float(point.plant_temperature) if point.plant_temperature else None,
            one_hour_fuel=float(point.one_hour_fuel) if point.one_hour_fuel else None,
            ten_hour_fuel=float(point.ten_hour_fuel) if point.ten_hour_fuel else None,
            hundred_hour_fuel=float(point.hundred_hour_fuel) if point.hundred_hour_fuel else None,
            fire_risk=fire_risk
        )
        heatmap_points.append(heatmap_point)
    
    return HeatmapDataResponse(
        scan_id=scan_id,
        total_points=len(heatmap_points),
        data_points=heatmap_points
    )
