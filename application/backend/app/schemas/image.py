from pydantic import BaseModel
from typing import Optional


class ImageUploadResponse(BaseModel):
    image_id: int
    file_path: str
    url: str
    fuel_estimation: Optional[dict] = None
    message: str = "Image uploaded successfully"
