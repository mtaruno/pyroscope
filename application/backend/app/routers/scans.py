from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.schemas.scan import (
    ScanCreate,
    ScanResponse,
    ScanListResponse,
    ScanListItem,
    ImageInfo,
    LatestCaptureResponse,
    WaypointSampleItem,
    ScanSamplesResponse,
)
from app.schemas.response import ScanCreateResponse
from app.schemas.heatmap import HeatmapDataResponse, HeatmapPoint
from app.services.scan_service import ScanService
from app.services.fire_risk_service import FireRiskService
from app.utils.validators import validate_risk_level
from app.models.scan import ScanRecord
from app.models.environmental import EnvironmentalData
from app.models.waypoint_sample import ScanWaypointSample
from app.models.image import ScanImage, ImageType

router = APIRouter(prefix="/scans", tags=["Scans"])

def _as_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
            fuel_load=_as_float(scan.fuel_load)                                            # ✅ 添加
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
        fuel_load=_as_float(scan.fuel_load),
        fuel_density=float(scan.fuel_density) if scan.fuel_density else None,
        biomass=float(scan.biomass) if scan.biomass else None,
        one_hour_fuel=_as_float(scan.one_hour_fuel),
        ten_hour_fuel=_as_float(scan.ten_hour_fuel),
        hundred_hour_fuel=_as_float(scan.hundred_hour_fuel),
        pine_cone_count=scan.pine_cone_count,
        robot_id=scan.robot_id,
        completed_at=scan.completed_at,
        created_at=scan.created_at,
        images=image_infos
    )


@router.get("/{scan_id}/latest-capture", response_model=LatestCaptureResponse)
async def get_latest_capture(scan_id: int, db: Session = Depends(get_db)):
    """Get the latest waypoint capture for a scan (sample data + thermal + RGB image URLs)."""
    scan = db.query(ScanRecord).filter(ScanRecord.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    latest = (
        db.query(ScanWaypointSample)
        .filter(ScanWaypointSample.scan_id == scan_id)
        .order_by(ScanWaypointSample.sequence_index.desc())
        .first()
    )
    thermal_img = (
        db.query(ScanImage)
        .filter(ScanImage.scan_id == scan_id, ScanImage.image_type == ImageType.thermal_latest)
        .first()
    )
    thermal_url = f"/api/images/{thermal_img.id}" if thermal_img else None
    rgb_url = f"/api/images/{latest.rgb_image_id}" if latest and latest.rgb_image_id else None
    if not latest:
        return LatestCaptureResponse(thermal_image_url=thermal_url)
    return LatestCaptureResponse(
        air_temperature=float(latest.air_temperature) if latest.air_temperature is not None else None,
        air_humidity=float(latest.air_humidity) if latest.air_humidity is not None else None,
        thermal_mean=float(latest.thermal_mean) if latest.thermal_mean is not None else None,
        captured_at=latest.captured_at,
        thermal_image_url=thermal_url,
        rgb_image_url=rgb_url,
    )


@router.get("/{scan_id}/samples", response_model=ScanSamplesResponse)
async def get_scan_samples(
    scan_id: int,
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Get all waypoint samples for a scan (paginated)."""
    scan = db.query(ScanRecord).filter(ScanRecord.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    total = db.query(ScanWaypointSample).filter(ScanWaypointSample.scan_id == scan_id).count()
    rows = (
        db.query(ScanWaypointSample)
        .filter(ScanWaypointSample.scan_id == scan_id)
        .order_by(ScanWaypointSample.sequence_index)
        .offset(offset)
        .limit(limit)
        .all()
    )
    samples = [
        WaypointSampleItem(
            sequence_index=r.sequence_index,
            captured_at=r.captured_at,
            air_temperature=float(r.air_temperature) if r.air_temperature is not None else None,
            air_humidity=float(r.air_humidity) if r.air_humidity is not None else None,
            thermal_mean=float(r.thermal_mean) if r.thermal_mean is not None else None,
            rgb_image_url=f"/api/images/{r.rgb_image_id}" if r.rgb_image_id else None,
        )
        for r in rows
    ]
    return ScanSamplesResponse(scan_id=scan_id, total=total, samples=samples)


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
    
    # Get environmental data points (from manual upload / legacy flow)
    env_data = db.query(EnvironmentalData).filter(
        EnvironmentalData.scan_id == scan_id
    ).all()

    # Also get waypoint samples (from real robot capture)
    waypoint_data = db.query(ScanWaypointSample).filter(
        ScanWaypointSample.scan_id == scan_id
    ).all()

    heatmap_points = []

    # Add environmental data points
    for point in env_data:
        fire_risk = FireRiskService.calculate_fire_risk(
            plant_temperature=float(point.plant_temperature) if point.plant_temperature else None,
            air_humidity=float(point.air_humidity) if point.air_humidity else None,
            one_hour_fuel=float(point.one_hour_fuel) if point.one_hour_fuel else None,
            ten_hour_fuel=float(point.ten_hour_fuel) if point.ten_hour_fuel else None,
            hundred_hour_fuel=float(point.hundred_hour_fuel) if point.hundred_hour_fuel else None
        )
        heatmap_points.append(HeatmapPoint(
            latitude=float(point.latitude) if point.latitude else 0,
            longitude=float(point.longitude) if point.longitude else 0,
            air_temperature=float(point.air_temperature) if point.air_temperature else None,
            air_humidity=float(point.air_humidity) if point.air_humidity else None,
            plant_temperature=float(point.plant_temperature) if point.plant_temperature else None,
            one_hour_fuel=float(point.one_hour_fuel) if point.one_hour_fuel else None,
            ten_hour_fuel=float(point.ten_hour_fuel) if point.ten_hour_fuel else None,
            hundred_hour_fuel=float(point.hundred_hour_fuel) if point.hundred_hour_fuel else None,
            fire_risk=fire_risk
        ))

    # Add waypoint sample data (from real robot captures)
    if waypoint_data and not env_data:
        # Use scan's lat/lng as base, spread waypoints in a grid for visualization
        base_lat = float(scan.latitude) if scan.latitude else 0
        base_lng = float(scan.longitude) if scan.longitude else 0
        area_m = 50.0  # Match 50m inner boundary shown on heatmap map
        deg_per_m = 1.0 / 111000.0
        half_span = (area_m / 2.0) * deg_per_m

        n = len(waypoint_data)
        cols = max(1, int(n ** 0.5))
        for i, wp in enumerate(waypoint_data):
            row = i // cols
            col = i % cols
            lat = base_lat - half_span + (row / max(1, cols - 1)) * 2 * half_span if cols > 1 else base_lat
            lng = base_lng - half_span + (col / max(1, cols - 1)) * 2 * half_span if cols > 1 else base_lng

            fire_risk = FireRiskService.calculate_fire_risk(
                plant_temperature=float(wp.thermal_mean) if wp.thermal_mean else None,
                air_humidity=float(wp.air_humidity) if wp.air_humidity else None,
            )
            heatmap_points.append(HeatmapPoint(
                latitude=lat,
                longitude=lng,
                air_temperature=float(wp.air_temperature) if wp.air_temperature else None,
                air_humidity=float(wp.air_humidity) if wp.air_humidity else None,
                plant_temperature=float(wp.thermal_mean) if wp.thermal_mean else None,
                one_hour_fuel=None,
                ten_hour_fuel=None,
                hundred_hour_fuel=None,
                fire_risk=fire_risk
            ))

    return HeatmapDataResponse(
        scan_id=scan_id,
        total_points=len(heatmap_points),
        data_points=heatmap_points
    )
