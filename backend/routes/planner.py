from datetime import date, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    DailyState,
    Goal,
    Outcome,
    Prediction,
    Task,
    TaskSession,
    User,
)
from ..schemas import ScheduleItemResponse
from ..services.scheduler import generate_schedule

router = APIRouter(prefix="/planner", tags=["Planner"])


@router.get(
    "/generate/{user_id}",
    response_model=list[ScheduleItemResponse]
)
def generate_user_schedule(
    user_id: int,
    available_hours: float | None = None,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return []

    tasks = (
        db.query(Task)
        .filter(
            Task.user_id == user_id,
            Task.status == "pending"
        )
        .all()
    )
    goals_by_id = {
        goal.id: goal
        for goal in db.query(Goal).filter(Goal.user_id == user_id).all()
    }

    # The planner uses ONLY today's life state.
    # Previous days remain historical records for learning.
    daily_state = (
        db.query(DailyState)
        .filter(
            DailyState.user_id == user_id,
            DailyState.date == date.today()
        )
        .first()
    )

    task_history = {}

    for task in tasks:
        sessions = (
            db.query(TaskSession)
            .filter(
                TaskSession.task_id == task.id,
                TaskSession.actual_duration.isnot(None)
            )
            .all()
        )

        outcomes = (
            db.query(Outcome)
            .join(TaskSession)
            .filter(TaskSession.task_id == task.id)
            .all()
        )

        durations = [
            s.actual_duration
            for s in sessions
            if s.actual_duration is not None
        ]

        completion_rates = [
            1.0 if o.completed else 0.0
            for o in outcomes
        ]

        task_history[task.id] = {
            "durations": durations,
            "completion_rates": completion_rates
        }

    if available_hours is not None:
        hours = available_hours
    elif daily_state and daily_state.available_hours is not None:
        hours = daily_state.available_hours
    else:
        hours = user.available_hours

    schedule = generate_schedule(
        tasks=tasks,
        daily_state=daily_state,
        goals_by_id=goals_by_id,
        available_hours=hours,
        start_time=user.preferred_start_time,
        task_history=task_history
    )

    # Store the prediction used for this plan.
    # Existing history is never deleted.
    for item in schedule:
        prediction = Prediction(
            task_id=item["task_id"],
            predicted_duration=item["predicted_duration"],
            completion_probability=item["completion_probability"],
            prediction_time=datetime.utcnow(),
            model_version=item.get("model_version", "baseline-v1")
        )
        db.add(prediction)

    db.commit()

    return schedule
