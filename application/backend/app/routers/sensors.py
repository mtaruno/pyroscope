from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from typing import Optional
import json
from pathlib import Path

from app.config import settings
from app.services.ros_sensor_bridge import (
    get_latest_from_ros,
    get_required_topics_status,
    get_live_rgb_bytes,
    get_live_thermal_bytes,
    _ros_cache,
    _ros_thread,
)

router = APIRouter(prefix="/sensors", tags=["Sensors"])

# Fallback paths for standalone script mode (no ROS)
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


class SensorAvailability(BaseModel):
    available: bool = False
    missing_topics: list[str] = []


@router.get("/latest", response_model=SensorData)
async def get_latest_sensors():
    """Get latest sensor readings from all sensors"""
    try:
        if not SENSOR_DATA_FILE.exists():
            return SensorData()
        with open(SENSOR_DATA_FILE, 'r') as f:
            data = json.load(f)
        return SensorData(**data)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read sensor data: {str(e)}"
        )


@router.get("/availability", response_model=SensorAvailability)
async def get_sensor_availability():
    """Check whether required sensor ROS topics are currently available."""
    status = get_required_topics_status()
    return SensorAvailability(**status)


@router.get("/thermal/image")
async def get_thermal_image():
    """Get latest thermal camera image (fallback file-based)"""
    if not THERMAL_IMAGE_PATH.exists():
        raise HTTPException(status_code=404, detail="Thermal image not available")
    return FileResponse(THERMAL_IMAGE_PATH, media_type="image/jpeg", headers={"Cache-Control": "no-cache"})


@router.get("/rgb/image")
async def get_rgb_image():
    """Get latest RGB camera image (fallback file-based)"""
    if not RGB_IMAGE_PATH.exists():
        raise HTTPException(status_code=404, detail="RGB image not available")
    return FileResponse(RGB_IMAGE_PATH, media_type="image/jpeg", headers={"Cache-Control": "no-cache"})


@router.get("/live-snapshot", response_model=SensorData)
async def get_live_snapshot():
    """Live ROS topic snapshot: temperature, humidity, thermal_mean + image URLs."""
    data = get_latest_from_ros()

    # Fall back to JSON file when ROS bridge cache is empty
    has_sensor_data = any(data.get(k) is not None for k in ("temperature", "humidity", "thermal_mean"))
    if not has_sensor_data and SENSOR_DATA_FILE.exists():
        try:
            with open(SENSOR_DATA_FILE, 'r') as f:
                data = json.load(f)
        except Exception:
            pass

    # Check in-memory bytes first, then fallback file paths
    thermal_image_url = (
        "/api/sensors/live/thermal" if get_live_thermal_bytes() is not None
        else ("/api/sensors/thermal/image" if THERMAL_IMAGE_PATH.exists() else None)
    )
    rgb_image_url = (
        "/api/sensors/live/rgb" if get_live_rgb_bytes() is not None
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
    """Serve latest thermal image directly from memory (no disk I/O)."""
    jpeg_bytes = get_live_thermal_bytes()
    if jpeg_bytes is None:
        raise HTTPException(status_code=404, detail="Thermal image not available")
    return Response(content=jpeg_bytes, media_type="image/jpeg", headers={"Cache-Control": "no-cache"})


@router.get("/live/rgb")
async def get_live_rgb_image():
    """Serve latest RGB image directly from memory (no disk I/O)."""
    jpeg_bytes = get_live_rgb_bytes()
    if jpeg_bytes is None:
        raise HTTPException(status_code=404, detail="RGB image not available")
    return Response(content=jpeg_bytes, media_type="image/jpeg", headers={"Cache-Control": "no-cache"})


@router.get("/debug/image-pipeline")
async def debug_image_pipeline():
    """Diagnostic: check image pipeline state."""
    with _ros_cache["lock"]:
        rgb_bytes = _ros_cache["rgb_image_bytes"]
        thermal_bytes = _ros_cache["thermal_image_bytes"]
    return {
        "ros_bridge_thread_alive": _ros_thread is not None and _ros_thread.is_alive(),
        "rgb_in_memory": rgb_bytes is not None,
        "rgb_bytes_size": len(rgb_bytes) if rgb_bytes else 0,
        "thermal_in_memory": thermal_bytes is not None,
        "thermal_bytes_size": len(thermal_bytes) if thermal_bytes else 0,
        "fallback_rgb_exists": RGB_IMAGE_PATH.exists(),
        "fallback_thermal_exists": THERMAL_IMAGE_PATH.exists(),
    }
