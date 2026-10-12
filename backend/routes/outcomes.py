from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Outcome, Prediction, Task, TaskSession

router = APIRouter(prefix="/outcomes", tags=["Outcomes"])

@router.get("/user/{user_id}")
def get_user_outcomes(user_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(Outcome, TaskSession, Task)
        .join(TaskSession, Outcome.task_session_id == TaskSession.id)
        .join(Task, TaskSession.task_id == Task.id)
        .filter(Task.user_id == user_id)
        .order_by(Outcome.id.desc())
        .all()
    )
    result = []
    for outcome, session, task in rows:
        prediction = db.query(Prediction).filter(
            Prediction.task_id == task.id,
            Prediction.prediction_time <= outcome.created_at
        ).order_by(Prediction.prediction_time.desc()).first()
        predicted = prediction.predicted_duration if prediction else None
        error = abs(float(outcome.actual_duration) - float(predicted)) if predicted is not None else None
        result.append({
            "outcome_id": outcome.id,
            "task_id": task.id,
            "title": task.title,
            "predicted_duration": predicted,
            "actual_duration": outcome.actual_duration,
            "duration_error": round(error, 2) if error is not None else None,
            "duration_error_percent": round((error / predicted) * 100, 1) if error is not None and predicted else None,
            "completed": outcome.completed,
            "user_rating": outcome.user_rating,
            "notes": outcome.notes,
            "created_at": outcome.created_at,
        })
    return result

@router.post("/{task_id}")
def record_task_outcome(task_id: int, actual_duration: float, completed: bool, user_rating: float | None = None, notes: str | None = None, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    session = TaskSession(task_id=task_id, start_time=None, end_time=None, actual_duration=actual_duration)
    db.add(session)
    db.flush()
    outcome = Outcome(
        task_session_id=session.id,
        completed=completed,
        actual_duration=actual_duration,
        user_rating=user_rating,
        notes=notes,
        created_at=datetime.utcnow(),
    )
    db.add(outcome)
    if completed:
        task.status = "completed"
    db.commit()
    return {"message": "Outcome recorded successfully", "task_id": task_id, "actual_duration": actual_duration, "completed": completed}
