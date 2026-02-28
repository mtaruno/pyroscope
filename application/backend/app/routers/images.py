from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import json
from app.database import get_db
from app.models.scan import ScanRecord
from app.models.image import ScanImage
from app.schemas.image import ImageUploadResponse
from app.services.image_service import ImageService
from app.utils.validators import validate_image_type
from app.utils.file_handler import validate_image_file
import os

router = APIRouter(prefix="/images", tags=["Images"])


@router.post("/upload", response_model=ImageUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_image(
    scan_id: int = Form(...),
    image_type: str = Form(...),
    file: UploadFile = File(...),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    captured_at: Optional[str] = Form(None),
    metadata: Optional[str] = Form(None),
    estimate_fuel: Optional[bool] = Form(False),
    db: Session = Depends(get_db)
):
    """Upload an image for a scan"""
    # Validate file
    validate_image_file(file)
    
    # Validate image type
    image_type = validate_image_type(image_type)
    
    # Verify scan exists
    scan = db.query(ScanRecord).filter(ScanRecord.id == scan_id).first()
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found"
        )
    
    # Save image file
    image_service = ImageService()
    file_info = await image_service.save_image(file, scan_id, image_type)
    
    # Parse metadata if provided
    metadata_dict = None
    if metadata:
        try:
            metadata_dict = json.loads(metadata)
        except json.JSONDecodeError:
            pass
    
    # Parse captured_at
    captured_datetime = None
    if captured_at:
        try:
            captured_datetime = datetime.fromisoformat(captured_at.replace('Z', '+00:00'))
        except ValueError:
            pass
    
    # Create database record
    scan_image = ScanImage(
        scan_id=scan_id,
        image_type=image_type,
        file_path=file_info["file_path"],
        file_size=file_info["file_size"],
        mime_type=file_info["mime_type"],
        width=file_info["width"],
        height=file_info["height"],
        latitude=latitude,
        longitude=longitude,
        captured_at=captured_datetime,
        meta_data=metadata_dict
    )
    
    db.add(scan_image)
    db.commit()
    db.refresh(scan_image)
    
    fuel_estimation = None
    if estimate_fuel:
        fuel_estimation = image_service.estimate_fuel_for_scan(db, scan_id)

    return ImageUploadResponse(
        image_id=scan_image.id,
        file_path=file_info["file_path"],
        url=f"/api/images/{scan_image.id}",
        fuel_estimation=fuel_estimation if fuel_estimation and fuel_estimation.get("success") else None,
    )


@router.get("/{image_id}")
async def get_image(image_id: int, db: Session = Depends(get_db)):
    """Get image file by ID"""
    image = db.query(ScanImage).filter(ScanImage.id == image_id).first()
    
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found"
        )
    
    if not os.path.exists(image.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image file not found on disk"
        )
    
    return FileResponse(
        image.file_path,
        media_type=image.mime_type or "image/jpeg"
    )


@router.post("/estimate-fuel/{scan_id}")
async def estimate_fuel_for_scan(scan_id: int, db: Session = Depends(get_db)):
    """Estimate fuel load for all visible images in a scan and backfill scan record."""
    scan = db.query(ScanRecord).filter(ScanRecord.id == scan_id).first()
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found",
        )

    image_service = ImageService()
    result = image_service.estimate_fuel_for_scan(db, scan_id)
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Fuel estimation failed"),
        )
    return result
