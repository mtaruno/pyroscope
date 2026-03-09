import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import scans, environmental, images, robot, sensors
from app.services.ros_sensor_bridge import is_ros_configured, start_ros_bridge

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Pyroscope Dashboard API",
    description="Backend API for wildfire monitoring robot data collection",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(scans.router, prefix="/api")
app.include_router(environmental.router, prefix="/api")
app.include_router(images.router, prefix="/api")
app.include_router(robot.router, prefix="/api")
app.include_router(sensors.router, prefix="/api")


@app.on_event("startup")
def startup_ros_bridge():
    """Auto-start ROS sensor bridge if ROS_MASTER_URI is configured."""
    print(f"[STARTUP] ROS_MASTER_URI={settings.ROS_MASTER_URI!r}, ROS_IP={settings.ROS_IP!r}")
    if is_ros_configured():
        upload_dir = settings.UPLOAD_DIR
        thermal_dir = os.path.join(upload_dir, "thermal_latest")
        rgb_dir = os.path.join(upload_dir, "realsense_latest")
        os.makedirs(thermal_dir, exist_ok=True)
        os.makedirs(rgb_dir, exist_ok=True)
        started = start_ros_bridge(thermal_dir, rgb_dir)
        print(f"[STARTUP] ROS sensor bridge {'STARTED' if started else 'FAILED TO START'}")
    else:
        print("[STARTUP] ROS not configured — sensor bridge NOT started")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Pyroscope Dashboard API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}
