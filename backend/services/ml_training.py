import json
from datetime import date, datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sqlalchemy.orm import joinedload

from ..models import DailyState, Outcome, Task, TaskSession
from .ml_features import FEATURE_NAMES, build_task_features


MODEL_VERSION = "ml-rf-v1"
MIN_TRAINING_SAMPLES = 8
MODEL_DIR = Path(__file__).resolve().parents[1] / "ml_models"
ARTIFACT_NAMES = {
    "duration": "duration_model.joblib",
    "completion": "completion_model.joblib",
}


def _reference_datetime(outcome, session):
    return session.end_time or session.start_time or outcome.created_at


def collect_training_samples(db, user_id=None):
    state_query = db.query(DailyState).order_by(DailyState.id.asc())
    if user_id is not None:
        state_query = state_query.filter(DailyState.user_id == user_id)

    states_by_user_date = {}
    for state in state_query.all():
        states_by_user_date[(state.user_id, state.date)] = state

    outcome_query = (
        db.query(Outcome)
        .join(TaskSession)
        .join(Task)
        .options(joinedload(Outcome.task_session).joinedload(TaskSession.task))
    )
    if user_id is not None:
        outcome_query = outcome_query.filter(Task.user_id == user_id)

    outcomes = outcome_query.all()
    outcomes.sort(
        key=lambda outcome: (
            _reference_datetime(outcome, outcome.task_session)
            or datetime.min,
            outcome.id,
        )
    )

    prior_durations = {}
    prior_completion = {}
    samples = []
    today = date.today()

    for outcome in outcomes:
        session = outcome.task_session
        task = session.task
        timestamp = _reference_datetime(outcome, session)
        duration = outcome.actual_duration
        if duration is None:
            duration = session.actual_duration
        if (
            timestamp is None
            or timestamp.date() > today
            or duration is None
            or float(duration) <= 0
            or outcome.completed is None
        ):
            continue

        daily_state = states_by_user_date.get((task.user_id, timestamp.date()))
        if daily_state is None:
            continue

        task_durations = prior_durations.setdefault(task.id, [])
        task_completion = prior_completion.setdefault(task.id, [])
        samples.append({
            "features": build_task_features(
                task,
                daily_state,
                task_durations,
                task_completion,
            ),
            "duration": float(duration),
            "completed": int(bool(outcome.completed)),
            "user_id": task.user_id,
        })
        task_durations.append(float(duration))
        task_completion.append(int(bool(outcome.completed)))

    return samples


def _feature_frame(samples):
    return pd.DataFrame(
        [sample["features"] for sample in samples],
        columns=FEATURE_NAMES,
    )


def _make_pipeline(model_type):
    preprocessing = ColumnTransformer(
        [("category", OneHotEncoder(handle_unknown="ignore"), ["category"])],
        remainder="passthrough",
    )
    if model_type == "duration":
        estimator = RandomForestRegressor(
            n_estimators=80,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=1,
        )
    else:
        estimator = RandomForestClassifier(
            n_estimators=80,
            min_samples_leaf=2,
            class_weight="balanced",
            random_state=42,
            n_jobs=1,
        )
    return Pipeline([("preprocessing", preprocessing), ("model", estimator)])


def _split_indices(targets, model_type):
    indices = list(range(len(targets)))
    stratify = None
    if model_type == "completion":
        values = pd.Series(targets).value_counts()
        if len(values) < 2 or values.min() < 2:
            return None
        stratify = targets
    try:
        return train_test_split(
            indices,
            test_size=0.25,
            random_state=42,
            stratify=stratify,
        )
    except ValueError:
        return None


def _train_one(samples, model_type, model_dir=None):
    model_dir = Path(model_dir or MODEL_DIR)
    target_key = "duration" if model_type == "duration" else "completed"
    targets = [sample[target_key] for sample in samples]
    sample_count = len(samples)
    result = {
        "trained": False,
        "status": "insufficient_data",
        "model_version": "baseline-v1",
        "samples": sample_count,
        "feature_names": FEATURE_NAMES.copy(),
    }

    if sample_count < MIN_TRAINING_SAMPLES:
        return result

    split = _split_indices(targets, model_type)
    if split is None:
        return result
    train_indices, test_indices = split
    features = _feature_frame(samples)
    estimator = _make_pipeline(model_type)
    estimator.fit(features.iloc[train_indices], [targets[i] for i in train_indices])
    predictions = estimator.predict(features.iloc[test_indices])
    actual = [targets[i] for i in test_indices]

    if model_type == "duration":
        result["mae"] = float(mean_absolute_error(actual, predictions))
        result["r2"] = (
            float(r2_score(actual, predictions)) if len(actual) >= 2 else None
        )
    else:
        result["accuracy"] = float(accuracy_score(actual, predictions))
        result["f1"] = float(f1_score(actual, predictions, zero_division=0))

    final_estimator = _make_pipeline(model_type)
    final_estimator.fit(features, targets)
    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": final_estimator,
            "model_version": MODEL_VERSION,
            "user_id": samples[0]["user_id"],
            "feature_names": FEATURE_NAMES.copy(),
        },
        model_dir / ARTIFACT_NAMES[model_type],
    )
    result.update({
        "trained": True,
        "status": "trained",
        "model_version": MODEL_VERSION,
    })
    return result


def train_duration_model(db, user_id=None, model_dir=None):
    samples = collect_training_samples(db, user_id)
    return _train_one(samples, "duration", model_dir)


def train_completion_model(db, user_id=None, model_dir=None):
    samples = collect_training_samples(db, user_id)
    return _train_one(samples, "completion", model_dir)


def train_models(db, user_id=None, model_dir=None):
    model_dir = Path(model_dir or MODEL_DIR)
    duration = train_duration_model(db, user_id, model_dir)
    completion = train_completion_model(db, user_id, model_dir)
    trained = duration["trained"] and completion["trained"]
    metadata = {
        "status": "trained" if trained else "not_trained",
        "model_version": MODEL_VERSION if trained else "baseline-v1",
        "trained_at": datetime.now(timezone.utc).isoformat() if trained else None,
        "user_id": user_id,
        "duration_model_trained": duration["trained"],
        "completion_model_trained": completion["trained"],
        "duration_samples": duration["samples"],
        "completion_samples": completion["samples"],
        "duration_mae": duration.get("mae"),
        "duration_r2": duration.get("r2"),
        "completion_accuracy": completion.get("accuracy"),
        "completion_f1": completion.get("f1"),
        "feature_names": FEATURE_NAMES.copy(),
    }
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "model_metadata.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )
    return metadata


def load_model(model_type, model_dir=None):
    if model_type not in ARTIFACT_NAMES:
        return None
    path = Path(model_dir or MODEL_DIR) / ARTIFACT_NAMES[model_type]
    try:
        artifact = joblib.load(path)
    except Exception:
        return None
    if not isinstance(artifact, dict) or "model" not in artifact:
        return None
    return artifact


def load_model_metadata(model_dir=None):
    path = Path(model_dir or MODEL_DIR) / "model_metadata.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None