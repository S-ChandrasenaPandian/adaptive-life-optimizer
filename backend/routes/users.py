from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User
from ..schemas import UserCreate, UserResponse, UserUpdate


router = APIRouter(
    prefix="/users",
    tags=["Users"]
)


@router.post("/", response_model=UserResponse)
def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    user = User(
        name=user_data.name,
        available_hours=user_data.available_hours,
        normal_sleep_hours=user_data.normal_sleep_hours,
        preferred_start_time=user_data.preferred_start_time
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.get("/", response_model=list[UserResponse])
def get_users(db: Session = Depends(get_db)):
    return db.query(User).all()

@router.put("/{user_id}")
def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    if user_data.name is not None:
        user.name = user_data.name

    if user_data.available_hours is not None:
        user.available_hours = user_data.available_hours

    if user_data.normal_sleep_hours is not None:
        user.normal_sleep_hours = user_data.normal_sleep_hours

    if user_data.preferred_start_time is not None:
        user.preferred_start_time = user_data.preferred_start_time

    db.commit()
    db.refresh(user)

    return user