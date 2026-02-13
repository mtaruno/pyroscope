from pydantic import BaseModel
from typing import Optional


class ImageUploadResponse(BaseModel):
    image_id: int
    file_path: str
    url: str
    message: str = "Image uploaded successfully"
