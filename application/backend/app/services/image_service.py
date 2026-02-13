from fastapi import UploadFile
import os
from datetime import datetime
from PIL import Image
import hashlib
from app.config import settings
from app.utils.file_handler import ensure_upload_directory


class ImageService:
    def __init__(self, upload_dir: str = None):
        self.upload_dir = upload_dir or settings.UPLOAD_DIR
    
    async def save_image(self, file: UploadFile, scan_id: int, image_type: str) -> dict:
        """Save uploaded image and return file information"""
        # Generate file path: uploads/thermal/2026/02/07/
        date_path = datetime.now().strftime("%Y/%m/%d")
        type_dir = os.path.join(self.upload_dir, image_type, date_path)
        ensure_upload_directory(type_dir)
        
        # Generate unique filename
        file_ext = os.path.splitext(file.filename)[1]
        file_hash = hashlib.md5(f"{scan_id}_{datetime.now().isoformat()}".encode()).hexdigest()[:8]
        filename = f"{image_type}_{scan_id}_{file_hash}{file_ext}"
        file_path = os.path.join(type_dir, filename)
        
        # Save file
        content = await file.read()
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        
        # Get image dimensions
        try:
            with Image.open(file_path) as img:
                width, height = img.size
        except Exception:
            width, height = None, None
        
        return {
            "file_path": file_path,
            "file_size": os.path.getsize(file_path),
            "width": width,
            "height": height,
            "mime_type": file.content_type
        }
