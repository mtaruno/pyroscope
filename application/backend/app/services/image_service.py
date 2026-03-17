from fastapi import UploadFile
import os
from datetime import datetime
from PIL import Image
import hashlib
import mimetypes
from typing import Optional, List, Dict, Any
import requests
from urllib.parse import urlparse, urlunparse
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
        fuels = result.get("fuels") if isinstance(result.get("fuels"), dict) else {}
        one_hour = self._to_float(
            result.get("one_hour_fuel", fuels.get("one_hour"))
        )
        ten_hour = self._to_float(
            result.get("ten_hour_fuel", fuels.get("ten_hour"))
        )
        hundred_hour = self._to_float(
            result.get("hundred_hour_fuel", fuels.get("hundred_hour"))
        )
        total = self._to_float(result.get("total_fuel_load", result.get("fuel_load")))
        if total is None:
            parts = [v for v in (one_hour, ten_hour, hundred_hour) if v is not None]
            total = sum(parts) if parts else None

        pine_cone_count = None
        if result.get("pine_cone_count") is not None:
            pine_cone_count = int(result["pine_cone_count"])
        elif isinstance(result.get("pines"), list):
            pine_cone_count = len(result["pines"])

        return {
            "total_fuel_load": total,
            "one_hour_fuel": one_hour,
            "ten_hour_fuel": ten_hour,
            "hundred_hour_fuel": hundred_hour,
            "pine_cone_count": pine_cone_count,
        }

    @staticmethod
    def _merge_fuel_estimation_metadata(image: ScanImage, result: Dict[str, Any]) -> None:
        meta_data = image.meta_data.copy() if isinstance(image.meta_data, dict) else {}
        meta_data["fuel_estimation"] = {
            "total_fuel_load": result.get("total_fuel_load"),
            "one_hour_fuel": result.get("one_hour_fuel"),
            "ten_hour_fuel": result.get("ten_hour_fuel"),
            "hundred_hour_fuel": result.get("hundred_hour_fuel"),
            "pine_cone_count": result.get("pine_cone_count"),
            "estimated_at": datetime.utcnow().isoformat(),
        }
        image.meta_data = meta_data

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
        parsed = urlparse(api_url)
        base_path = (parsed.path or "").strip()
        candidate_urls = [api_url.rstrip("/")]
        # If user configured only domain root, try known POST paths for this API.
        if base_path in ("", "/"):
            candidate_urls.extend([
                urlunparse((parsed.scheme, parsed.netloc, "/estimate", "", "", "")),
                urlunparse((parsed.scheme, parsed.netloc, "/upload", "", "", "")),
            ])
        # De-duplicate while keeping order.
        candidate_urls = list(dict.fromkeys(candidate_urls))

        last_error = None
        with open(image_path, "rb") as fp:
            for idx, candidate_url in enumerate(candidate_urls):
                if idx > 0:
                    fp.seek(0)
                files = {"file": (filename, fp, guessed_mime)}
                data = {"headless": str(bool(settings.FUEL_ESTIMATION_HEADLESS)).lower()}
                try:
                    resp = requests.post(
                        candidate_url,
                        files=files,
                        data=data,
                        headers=headers,
                        timeout=settings.FUEL_ESTIMATION_TIMEOUT,
                    )
                    # Retry another candidate only for method/path mismatch.
                    if resp.status_code in (404, 405):
                        last_error = f"{resp.status_code} on {candidate_url}"
                        continue
                    resp.raise_for_status()
                    payload = resp.json()
                    break
                except Exception as exc:
                    last_error = str(exc)
                    continue
            else:
                return {"success": False, "error": last_error or "Fuel API request failed"}

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
        errors: List[Dict[str, Any]] = []
        for image in images:
            result = self.estimate_fuel_for_image_path(image.file_path)
            if result.get("success"):
                self._merge_fuel_estimation_metadata(image, result)
                successful.append({
                    "image_id": image.id,
                    "file_path": image.file_path,
                    "total_fuel_load": result.get("total_fuel_load"),
                    "one_hour_fuel": result.get("one_hour_fuel"),
                    "ten_hour_fuel": result.get("ten_hour_fuel"),
                    "hundred_hour_fuel": result.get("hundred_hour_fuel"),
                    "pine_cone_count": result.get("pine_cone_count"),
                })
            else:
                errors.append({
                    "image_id": image.id,
                    "file_path": image.file_path,
                    "error": result.get("error", "Unknown fuel API error"),
                })

        if not successful:
            return {"success": False, "error": "; ".join(item["error"] for item in errors)}

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
            "per_image_results": successful,
        }
