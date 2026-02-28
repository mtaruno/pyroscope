from fastapi import UploadFile
import os
from datetime import datetime
from PIL import Image
import hashlib
import mimetypes
from typing import Optional, List, Dict, Any
import requests
from sqlalchemy.orm import Session
from app.config import settings
from app.utils.file_handler import ensure_upload_directory
from app.models.image import ScanImage, ImageType
from app.models.scan import ScanRecord


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

    @staticmethod
    def _to_float(value) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _extract_fuel_fields(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        result = payload.get("fuel_estimation") if isinstance(payload, dict) else None
        if not isinstance(result, dict):
            result = payload if isinstance(payload, dict) else {}
        return {
            "total_fuel_load": self._to_float(result.get("total_fuel_load", result.get("fuel_load"))),
            "one_hour_fuel": self._to_float(result.get("one_hour_fuel")),
            "ten_hour_fuel": self._to_float(result.get("ten_hour_fuel")),
            "hundred_hour_fuel": self._to_float(result.get("hundred_hour_fuel")),
            "pine_cone_count": int(result["pine_cone_count"]) if result.get("pine_cone_count") is not None else None,
        }

    def estimate_fuel_for_image_path(self, image_path: str) -> Dict[str, Any]:
        api_url = (settings.FUEL_ESTIMATION_API_URL or "").strip()
        if not api_url:
            return {"success": False, "error": "FUEL_ESTIMATION_API_URL is not configured"}
        if not os.path.exists(image_path):
            return {"success": False, "error": f"Image file not found: {image_path}"}

        headers = {}
        if settings.FUEL_ESTIMATION_API_KEY:
            headers["Authorization"] = f"Bearer {settings.FUEL_ESTIMATION_API_KEY}"

        guessed_mime = mimetypes.guess_type(image_path)[0] or "image/jpeg"
        filename = os.path.basename(image_path)
        with open(image_path, "rb") as fp:
            files = {"file": (filename, fp, guessed_mime)}
            data = {"headless": str(bool(settings.FUEL_ESTIMATION_HEADLESS)).lower()}
            try:
                resp = requests.post(
                    api_url,
                    files=files,
                    data=data,
                    headers=headers,
                    timeout=settings.FUEL_ESTIMATION_TIMEOUT,
                )
                resp.raise_for_status()
                payload = resp.json()
            except Exception as exc:
                return {"success": False, "error": str(exc)}

        parsed = self._extract_fuel_fields(payload)
        if parsed["total_fuel_load"] is None:
            return {
                "success": False,
                "error": "Fuel API returned no total_fuel_load",
                "raw": payload,
            }
        return {
            "success": True,
            **parsed,
            "raw": payload,
        }

    def estimate_fuel_for_scan(self, db: Session, scan_id: int) -> Dict[str, Any]:
        scan = db.query(ScanRecord).filter(ScanRecord.id == scan_id).first()
        if not scan:
            return {"success": False, "error": "Scan not found"}

        images: List[ScanImage] = (
            db.query(ScanImage)
            .filter(ScanImage.scan_id == scan_id, ScanImage.image_type == ImageType.visible)
            .order_by(ScanImage.created_at.desc())
            .all()
        )
        if not images:
            return {"success": False, "error": "No visible images found for scan"}

        successful: List[Dict[str, Any]] = []
        errors: List[str] = []
        for image in images:
            result = self.estimate_fuel_for_image_path(image.file_path)
            if result.get("success"):
                successful.append(result)
            else:
                errors.append(result.get("error", "Unknown fuel API error"))

        if not successful:
            return {"success": False, "error": "; ".join(errors)}

        def _avg(key: str) -> Optional[float]:
            values = [item.get(key) for item in successful if item.get(key) is not None]
            if not values:
                return None
            return sum(values) / len(values)

        total_fuel_load = _avg("total_fuel_load")
        one_hour_fuel = _avg("one_hour_fuel")
        ten_hour_fuel = _avg("ten_hour_fuel")
        hundred_hour_fuel = _avg("hundred_hour_fuel")
        pine_cone_values = [item.get("pine_cone_count") for item in successful if item.get("pine_cone_count") is not None]
        pine_cone_count = int(round(sum(pine_cone_values) / len(pine_cone_values))) if pine_cone_values else None

        if total_fuel_load is not None:
            scan.fuel_load = f"{total_fuel_load:.4f}"
        scan.one_hour_fuel = one_hour_fuel
        scan.ten_hour_fuel = ten_hour_fuel
        scan.hundred_hour_fuel = hundred_hour_fuel
        scan.pine_cone_count = pine_cone_count
        db.commit()
        db.refresh(scan)

        return {
            "success": True,
            "total_fuel_load": total_fuel_load,
            "one_hour_fuel": one_hour_fuel,
            "ten_hour_fuel": ten_hour_fuel,
            "hundred_hour_fuel": hundred_hour_fuel,
            "pine_cone_count": pine_cone_count,
            "processed_images": len(successful),
            "total_images": len(images),
            "errors": errors,
        }
