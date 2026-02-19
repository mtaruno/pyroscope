from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import scans, environmental, images, robot, sensors

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
