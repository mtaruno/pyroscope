from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class EnvironmentalDataCreate(BaseModel):
    air_temperature: Optional[float] = None
    air_humidity: Optional[float] = None
    wind_speed: Optional[float] = None
    plant_temperature: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    measured_at: datetime
    one_hour_fuel: Optional[float] = None
    ten_hour_fuel: Optional[float] = None
    hundred_hour_fuel: Optional[float] = None


class EnvironmentalBatchCreate(BaseModel):
    scan_id: int
    data: List[EnvironmentalDataCreate]
