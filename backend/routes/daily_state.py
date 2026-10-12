from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DailyState
from ..schemas import DailyStateCreate, DailyStateResponse

router = APIRouter(prefix="/daily-state", tags=["Daily State"])


@router.post("/", response_model=DailyStateResponse)
def save_daily_state(
    state_data: DailyStateCreate,
    db: Session = Depends(get_db)
):
    record_date = state_data.date_value or date.today()

    if state_data.available_hours is not None:
        if not 0 <= state_data.available_hours <= 24:
            raise HTTPException(
                status_code=400,
                detail="available_hours must be between 0 and 24"
            )

    state = (
        db.query(DailyState)
        .filter(
            DailyState.user_id == state_data.user_id,
            DailyState.date == record_date
        )
        .first()
    )

    values = {
        "available_hours": state_data.available_hours,
        "sleep_hours": state_data.sleep_hours,
        "energy": state_data.energy,
        "focus": state_data.focus,
        "workload": state_data.workload,
        "exercise_minutes": state_data.exercise_minutes,
    }

    if state:
        # Update the existing record for this user and date.
        for key, value in values.items():
            setattr(state, key, value)
    else:
        # Create a record for this user and date.
        state = DailyState(
            user_id=state_data.user_id,
            date=record_date,
            **values
        )
        db.add(state)

    db.commit()
    db.refresh(state)

    return state


@router.get("/", response_model=list[DailyStateResponse])
def get_daily_states(
    user_id: int | None = None,
    db: Session = Depends(get_db)
):
    query = db.query(DailyState)

    if user_id is not None:
        query = query.filter(DailyState.user_id == user_id)

    return query.order_by(
        DailyState.date.desc(),
        DailyState.id.desc()
    ).all()