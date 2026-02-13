from pydantic import BaseModel
from typing import Optional


class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None


class ScanCreateResponse(BaseModel):
    scan_id: int
    message: str = "Scan record created successfully"


class EnvironmentalDataResponse(BaseModel):
    inserted_count: int
    message: str = "Environmental data recorded successfully"


class RobotStatusResponse(BaseModel):
    status_id: int
    message: str = "Robot status recorded"
