from datetime import date, datetime, timedelta
from statistics import mean
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import DailyState, Outcome, Prediction, Task, TaskSession

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("/user/{user_id}")
def user_analytics(user_id: int, db: Session = Depends(get_db)):
    outcomes = (
        db.query(Outcome, TaskSession, Task)
        .join(TaskSession, Outcome.task_session_id == TaskSession.id)
        .join(Task, TaskSession.task_id == Task.id)
        .filter(Task.user_id == user_id)
        .all()
    )
    errors = []
    abs_pct = []
    completed = 0
    for outcome, session, task in outcomes:
        if outcome.completed:
            completed += 1
        prediction = db.query(Prediction).filter(
            Prediction.task_id == task.id,
            Prediction.prediction_time <= outcome.created_at
        ).order_by(Prediction.prediction_time.desc()).first()
        if prediction and prediction.predicted_duration:
            error = abs(float(outcome.actual_duration) - float(prediction.predicted_duration))
            errors.append(error)
            abs_pct.append((error / float(prediction.predicted_duration)) * 100)

    states = db.query(DailyState).filter(DailyState.user_id == user_id).order_by(DailyState.date.desc()).limit(14).all()
    return {
        "outcomes": len(outcomes),
        "completed_outcomes": completed,
        "completion_rate": round(completed / len(outcomes) * 100, 1) if outcomes else None,
        "prediction_pairs": len(errors),
        "mean_absolute_error_minutes": round(mean(errors), 1) if errors else None,
        "mean_absolute_percentage_error": round(mean(abs_pct), 1) if abs_pct else None,
        "daily_history": [
            {"date": s.date, "sleep": s.sleep_hours, "energy": s.energy, "focus": s.focus, "workload": s.workload, "exercise": s.exercise_minutes}
            for s in states
        ],
        "model": {
            "name": "Adaptive baseline predictor",
            "version": "adaptive-baseline-v3",
            "learning_signal": "historical task duration + completion outcomes",
            "note": "Prediction adapts toward observed behavior as outcome history accumulates."
        }
    }

@router.get("/predictions/{user_id}")
def prediction_history(user_id: int, db: Session = Depends(get_db)):
    tasks = db.query(Task).filter(Task.user_id == user_id).all()
    task_ids = [t.id for t in tasks]
    rows = db.query(Prediction).filter(Prediction.task_id.in_(task_ids)).order_by(Prediction.prediction_time.desc()).limit(100).all() if task_ids else []
    return [{
        "id": p.id,
        "task_id": p.task_id,
        "predicted_duration": p.predicted_duration,
        "completion_probability": p.completion_probability,
        "prediction_time": p.prediction_time,
        "model_version": p.model_version,
    } for p in rows]
