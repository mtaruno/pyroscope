from typing import Optional
from fastapi import HTTPException


def validate_risk_level(risk_level: Optional[str]) -> Optional[str]:
    """Validate risk level value"""
    if risk_level is None:
        return None
    
    valid_levels = ["low", "medium", "high"]
    if risk_level.lower() not in valid_levels:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid risk level. Must be one of: {', '.join(valid_levels)}"
        )
    
    return risk_level.lower()


def validate_image_type(image_type: str) -> str:
    """Validate image type value"""
    valid_types = ["thermal", "thermal_latest", "visible", "panorama", "detail"]
    if image_type.lower() not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid image type. Must be one of: {', '.join(valid_types)}"
        )
    
    return image_type.lower()


def validate_operating_state(state: Optional[str]) -> Optional[str]:
    """Validate robot operating state"""
    if state is None:
        return None
    
    valid_states = ["idle", "scanning", "charging", "error"]
    if state.lower() not in valid_states:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid operating state. Must be one of: {', '.join(valid_states)}"
        )
    
    return state.lower()
