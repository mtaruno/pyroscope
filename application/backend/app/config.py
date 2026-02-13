from pydantic_settings import BaseSettings
from typing import List
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
