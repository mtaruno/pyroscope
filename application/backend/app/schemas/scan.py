from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class FuelEstimationResult(BaseModel):
    """Fuel estimation result from external API"""
    success: bool
    total_fuel_load: Optional[float] = None
    one_hour_fuel: Optional[float] = None
    ten_hour_fuel: Optional[float] = None
    hundred_hour_fuel: Optional[float] = None
    pine_cone_count: Optional[int] = None
    error: Optional[str] = None


class ScanCreate(BaseModel):
    zone_id: str
    latitude: float
    longitude: float
    gps_accuracy: Optional[float] = None
    scan_area: Optional[str] = None
    duration: Optional[str] = None
    risk_level: Optional[str] = None
    avg_plant_temp: Optional[float] = None
    avg_air_temp: Optional[float] = None
    avg_humidity: Optional[float] = None
    wind_speed: Optional[float] = None
    temp_diff: Optional[float] = None
    fuel_load: Optional[float] = None
    fuel_density: Optional[float] = None
    biomass: Optional[float] = None
    one_hour_fuel: Optional[float] = None
    ten_hour_fuel: Optional[float] = None
    hundred_hour_fuel: Optional[float] = None
    pine_cone_count: Optional[int] = None
    robot_id: Optional[str] = None
    completed_at: Optional[datetime] = None


class ImageInfo(BaseModel):
    id: int
    image_type: str
    url: str
    captured_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ScanResponse(BaseModel):
    id: int
    zone_id: str
    latitude: float
    longitude: float
    gps_accuracy: Optional[float] = None
    scan_area: Optional[str] = None
    duration: Optional[str] = None
    risk_level: Optional[str] = None
    avg_plant_temp: Optional[float] = None
    avg_air_temp: Optional[float] = None
    avg_humidity: Optional[float] = None
    wind_speed: Optional[float] = None
    temp_diff: Optional[float] = None
    fuel_load: Optional[float] = None
    fuel_density: Optional[float] = None
    biomass: Optional[float] = None
    one_hour_fuel: Optional[float] = None
    ten_hour_fuel: Optional[float] = None
    hundred_hour_fuel: Optional[float] = None
    pine_cone_count: Optional[int] = None
    robot_id: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    images: Optional[List[ImageInfo]] = []
    
    class Config:
        from_attributes = True


class ScanListItem(BaseModel):
    id: int
    zone_id: str
    latitude: float
    longitude: float
    risk_level: Optional[str] = None
    completed_at: Optional[datetime] = None
    avg_air_temp: Optional[float] = None
    avg_humidity: Optional[float] = None
    avg_plant_temp: Optional[float] = None  # ✅ 添加
    fuel_load: Optional[float] = None        # ✅ 添加
    
    class Config:
        from_attributes = True


class ScanListResponse(BaseModel):
    total: int
    scans: List[ScanListItem]
