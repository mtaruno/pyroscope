from pydantic import BaseModel
from typing import List, Optional


class HeatmapPoint(BaseModel):
    """Single point data for heatmap rendering"""
    latitude: float
    longitude: float
    air_temperature: Optional[float] = None
    air_humidity: Optional[float] = None
    plant_temperature: Optional[float] = None
    one_hour_fuel: Optional[float] = None
    ten_hour_fuel: Optional[float] = None
    hundred_hour_fuel: Optional[float] = None
    fire_risk: Optional[float] = None  # Calculated value
    
    class Config:
        from_attributes = True


class HeatmapDataResponse(BaseModel):
    """Response containing all heatmap points for a scan"""
    scan_id: int
    total_points: int
    data_points: List[HeatmapPoint]
