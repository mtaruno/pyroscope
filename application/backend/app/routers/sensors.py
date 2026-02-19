from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import json
from pathlib import Path

router = APIRouter(prefix="/sensors", tags=["Sensors"])

# Path where ROS sensor bridge saves data
SENSOR_DATA_DIR = Path.home() / "Dev/pyroscope/application/backend/sensor_data"
SENSOR_DATA_FILE = SENSOR_DATA_DIR / "latest_sensors.json"
THERMAL_IMAGE_PATH = SENSOR_DATA_DIR / "thermal_latest.jpg"
RGB_IMAGE_PATH = SENSOR_DATA_DIR / "rgb_latest.jpg"


class SensorData(BaseModel):
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    thermal_mean: Optional[float] = None
    thermal_image_url: Optional[str] = None
    rgb_image_url: Optional[str] = None
    timestamp: Optional[float] = None


@router.get("/latest", response_model=SensorData)
async def get_latest_sensors():
    """Get latest sensor readings from all sensors"""
    try:
        if not SENSOR_DATA_FILE.exists():
            # Return empty data if sensor bridge not running yet
            return SensorData()

        with open(SENSOR_DATA_FILE, 'r') as f:
            data = json.load(f)

        return SensorData(**data)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read sensor data: {str(e)}"
        )


@router.get("/thermal/image")
async def get_thermal_image():
    """Get latest thermal camera image"""
    if not THERMAL_IMAGE_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="Thermal image not available"
        )

    return FileResponse(
        THERMAL_IMAGE_PATH,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache"}
    )


@router.get("/rgb/image")
async def get_rgb_image():
    """Get latest RGB camera image"""
    if not RGB_IMAGE_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="RGB image not available"
        )

    return FileResponse(
        RGB_IMAGE_PATH,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache"}
    )
