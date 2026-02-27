from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import json
from pathlib import Path

from app.config import settings
from app.services.ros_sensor_bridge import get_latest_from_ros

router = APIRouter(prefix="/sensors", tags=["Sensors"])

# Live ROS snapshot: images written by ros_sensor_bridge under UPLOAD_DIR
def _live_thermal_path():
    return Path(settings.UPLOAD_DIR) / "thermal_latest" / "ros_latest.jpg"
def _live_rgb_path():
    return Path(settings.UPLOAD_DIR) / "realsense_latest" / "ros_latest.jpg"

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


# Live ROS topic snapshot for scan modal (from ros_sensor_bridge cache + UPLOAD_DIR images)
@router.get("/live-snapshot", response_model=SensorData)
async def get_live_snapshot():
    """Live ROS topic snapshot: temperature, humidity, thermal_mean + image URLs."""
    data = get_latest_from_ros()

    # Fall back to JSON file written by standalone scripts/ros_sensor_bridge.py
    # when the in-process ROS bridge cache is empty.
    has_sensor_data = any(data.get(k) is not None for k in ("temperature", "humidity", "thermal_mean"))
    if not has_sensor_data and SENSOR_DATA_FILE.exists():
        try:
            with open(SENSOR_DATA_FILE, 'r') as f:
                data = json.load(f)
        except Exception:
            pass

    # Prefer in-process bridge image paths; fall back to standalone script paths.
    thermal_image_url = (
        "/api/sensors/live/thermal" if _live_thermal_path().exists()
        else ("/api/sensors/thermal/image" if THERMAL_IMAGE_PATH.exists() else None)
    )
    rgb_image_url = (
        "/api/sensors/live/rgb" if _live_rgb_path().exists()
        else ("/api/sensors/rgb/image" if RGB_IMAGE_PATH.exists() else None)
    )

    return SensorData(
        temperature=data.get("temperature"),
        humidity=data.get("humidity"),
        thermal_mean=data.get("thermal_mean"),
        thermal_image_url=thermal_image_url,
        rgb_image_url=rgb_image_url,
    )


@router.get("/live/thermal")
async def get_live_thermal_image():
    """Serve latest thermal image from ROS bridge (ros_latest.jpg)."""
    path = _live_thermal_path()
    if not path.exists():
        raise HTTPException(status_code=404, detail="Thermal image not available")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-cache"})


@router.get("/live/rgb")
async def get_live_rgb_image():
    """Serve latest RGB image from ROS bridge (ros_latest.jpg)."""
    path = _live_rgb_path()
    if not path.exists():
        raise HTTPException(status_code=404, detail="RGB image not available")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-cache"})
