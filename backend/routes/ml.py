from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Outcome, Prediction, Task, TaskSession
from ..services.ml_evaluation import evaluate_models
from ..services.ml_training import (
    ARTIFACT_NAMES,
    MODEL_DIR,
    load_model_metadata,
    train_models,
)


router = APIRouter(prefix="/ml", tags=["Machine Learning"])


@router.post("/train/{user_id}")
def train_user_models(user_id: int, db: Session = Depends(get_db)):
    return train_models(db, user_id=user_id)


@router.get("/status/{user_id}")
def get_ml_status(user_id: int):
    metadata = load_model_metadata()
    user_matches = metadata is not None and metadata.get("user_id") == user_id
    model_dir = Path(MODEL_DIR)
    duration_exists = (
        user_matches
        and metadata.get("duration_model_trained", False)
        and (model_dir / ARTIFACT_NAMES["duration"]).is_file()
    )
    completion_exists = (
        user_matches
        and metadata.get("completion_model_trained", False)
        and (model_dir / ARTIFACT_NAMES["completion"]).is_file()
    )
    trained = bool(duration_exists and completion_exists)

    return {
        "status": "trained" if trained else "not_trained",
        "models_exist": trained,
        "model_version": metadata.get("model_version") if trained else "not_trained",
        "trained_at": metadata.get("trained_at") if user_matches else None,
        "duration_samples": metadata.get("duration_samples", 0) if user_matches else 0,
        "completion_samples": metadata.get("completion_samples", 0) if user_matches else 0,
        "duration_mae": metadata.get("duration_mae") if user_matches else None,
        "duration_r2": metadata.get("duration_r2") if user_matches else None,
        "completion_accuracy": metadata.get("completion_accuracy") if user_matches else None,
        "completion_f1": metadata.get("completion_f1") if user_matches else None,
    }


@router.get("/evaluation/{user_id}")
def get_ml_evaluation(user_id: int, db: Session = Depends(get_db)):
    status = get_ml_status(user_id)
    prediction_rows = (
        db.query(Prediction, Task)
        .join(Task, Prediction.task_id == Task.id)
        .filter(Task.user_id == user_id)
        .order_by(Prediction.prediction_time.asc(), Prediction.id.asc())
        .all()
    )
    outcome_rows = (
        db.query(Outcome, TaskSession, Task)
        .join(TaskSession, Outcome.task_session_id == TaskSession.id)
        .join(Task, TaskSession.task_id == Task.id)
        .filter(Task.user_id == user_id)
        .order_by(Outcome.created_at.asc(), Outcome.id.asc())
        .all()
    )

    predictions_by_task = {}
    for prediction, task in prediction_rows:
        predictions_by_task.setdefault(task.id, []).append(prediction)

    matched_outcomes = {}
    for outcome, session, task in outcome_rows:
        eligible = [
            prediction
            for prediction in predictions_by_task.get(task.id, [])
            if prediction.prediction_time <= outcome.created_at
        ]
        if not eligible:
            continue
        prediction = eligible[-1]
        actual_duration = (
            outcome.actual_duration
            if outcome.actual_duration is not None
            else session.actual_duration
        )
        matched_outcomes[prediction.id] = {
            "outcome_id": outcome.id,
            "actual_duration": actual_duration,
            "completed": outcome.completed,
            "outcome_created_at": outcome.created_at,
        }

    prediction_history = []
    for prediction, task in reversed(prediction_rows):
        outcome = matched_outcomes.get(prediction.id)
        actual_duration = outcome["actual_duration"] if outcome else None
        predicted_duration = prediction.predicted_duration
        duration_error = (
            float(actual_duration) - float(predicted_duration)
            if actual_duration is not None and predicted_duration is not None
            else None
        )
        prediction_history.append({
            "prediction_id": prediction.id,
            "outcome_id": outcome["outcome_id"] if outcome else None,
            "task_id": task.id,
            "task_title": task.title,
            "predicted_duration": predicted_duration,
            "actual_duration": actual_duration,
            "duration_error": duration_error,
            "absolute_duration_error": abs(duration_error) if duration_error is not None else None,
            "completion_probability": prediction.completion_probability,
            "completed": outcome["completed"] if outcome else None,
            "model_version": prediction.model_version,
            "created_at": prediction.prediction_time,
            "outcome_created_at": outcome["outcome_created_at"] if outcome else None,
        })

    outcome_count = len(outcome_rows)
    completed_outcomes = sum(1 for outcome, _, _ in outcome_rows if outcome.completed)
    measured_duration_outcomes = sum(
        1
        for outcome, session, _ in outcome_rows
        if outcome.actual_duration is not None or session.actual_duration is not None
    )
    evaluation = evaluate_models(db, user_id=user_id) if status["models_exist"] else None

    return {
        "user_id": user_id,
        "model_version": status["model_version"],
        "models_exist": status["models_exist"],
        "trained_at": status["trained_at"],
        "training_samples": min(
            status["duration_samples"],
            status["completion_samples"],
        ) if status["models_exist"] else 0,
        "evaluation_samples": evaluation["duration_samples"] if evaluation else 0,
        "evaluated_at": datetime.now(timezone.utc),
        "duration": evaluation["duration"] if evaluation else {"mae": None, "r2": None},
        "completion": evaluation["completion"] if evaluation else {
            "accuracy": None,
            "precision": None,
            "recall": None,
            "f1": None,
        },
        "prediction_count": len(prediction_rows),
        "prediction_history": prediction_history,
        "feedback": {
            "outcomes_recorded": outcome_count,
            "completed_outcomes": completed_outcomes,
            "measured_duration_outcomes": measured_duration_outcomes,
            "available_for_future_training": evaluation["duration_samples"] if evaluation else 0,
            "automatic_retraining": False,
        },
    }