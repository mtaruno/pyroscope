from pydantic_settings import BaseSettings
from typing import List, Optional
import json


class Settings(BaseSettings):
    # Database Configuration
    DATABASE_URL: str
    
    # JWT Configuration
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 60
    
    # File Upload Configuration
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_IMAGE_TYPES: List[str] = ["image/jpeg", "image/png"]
    
    # CORS Configuration
    CORS_ORIGINS: str = '["http://localhost:5173"]'

    # ROS (optional): when set, backend subscribes to sensor topics on Jetson instead of subprocess
    # On PC: set ROS_MASTER_URI=http://<JETSON_IP>:11311 and ROS_IP=<PC_IP> (e.g. in .env)
    ROS_MASTER_URI: Optional[str] = ""
    ROS_IP: Optional[str] = ""

    # Fuel estimation (AI2/Wildlands API)
    FUEL_ESTIMATION_API_URL: Optional[str] = ""
    FUEL_ESTIMATION_TIMEOUT: int = 60
    FUEL_ESTIMATION_API_KEY: Optional[str] = ""
    FUEL_ESTIMATION_HEADLESS: bool = True
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS_ORIGINS from JSON string to list"""
        try:
            return json.loads(self.CORS_ORIGINS)
        except:
            return ["http://localhost:5173"]
    
    class Config:
        env_file = ".env"


settings = Settings()
