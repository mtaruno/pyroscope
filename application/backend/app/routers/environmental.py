from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.environmental import EnvironmentalData
from app.models.scan import ScanRecord
from app.schemas.environmental import EnvironmentalBatchCreate
from app.schemas.response import EnvironmentalDataResponse

router = APIRouter(prefix="/environmental", tags=["Environmental Data"])


@router.post("", response_model=EnvironmentalDataResponse, status_code=status.HTTP_201_CREATED)
async def upload_environmental_data(
    data: EnvironmentalBatchCreate,
    db: Session = Depends(get_db)
):
    """Upload batch environmental data for a scan"""
    # Verify scan exists
    scan = db.query(ScanRecord).filter(ScanRecord.id == data.scan_id).first()
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found"
        )
    
    # Insert environmental data
    environmental_records = []
    for item in data.data:
        record = EnvironmentalData(
            scan_id=data.scan_id,
            air_temperature=item.air_temperature,
            air_humidity=item.air_humidity,
            wind_speed=item.wind_speed,
            plant_temperature=item.plant_temperature,
            latitude=item.latitude,
            longitude=item.longitude,
            measured_at=item.measured_at
        )
        environmental_records.append(record)
    
    db.add_all(environmental_records)
    db.commit()
    
    return EnvironmentalDataResponse(inserted_count=len(environmental_records))
