from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.user import UserCreate, UserLogin, UserResponse, TokenResponse
from app.schemas.response import MessageResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    user = AuthService.create_user(db, user_data)
    return UserResponse(
        user_id=user.id,
        username=user.username,
        email=user.email,
        robot_id=user.robot_id
    )


@router.post("/login", response_model=TokenResponse)
async def login(login_data: UserLogin, db: Session = Depends(get_db)):
    """Login and get access token"""
    token_data = AuthService.authenticate_user(db, login_data)
    return TokenResponse(**token_data)
