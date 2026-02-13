from fastapi import UploadFile, HTTPException
from typing import Optional
import os
from app.config import settings


def validate_image_file(file: UploadFile) -> bool:
    """Validate image file type and size"""
    # Check file type
    if file.content_type not in settings.ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(settings.ALLOWED_IMAGE_TYPES)}"
        )
    
    return True


def ensure_upload_directory(path: str) -> None:
    """Ensure upload directory exists"""
    os.makedirs(path, exist_ok=True)
