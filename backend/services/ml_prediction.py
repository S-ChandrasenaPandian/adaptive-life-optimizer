import pandas as pd

from .ml_features import FEATURE_NAMES, build_task_features
from .ml_training import MODEL_DIR, load_model
from .prediction import predict_completion_probability, predict_duration


def _feature_frame(task, daily_state, historical_durations, historical_completion_rates):
    features = build_task_features(
        task,
        daily_state,
        historical_durations,
        historical_completion_rates,
    )
    return pd.DataFrame([features], columns=FEATURE_NAMES)


def _usable_model(model_type, task, model_dir=None):
    artifact = load_model(model_type, model_dir)
    if artifact is None:
        return None
    if artifact.get("user_id") != task.user_id:
        return None
    return artifact


def _duration_with_source(
    task,
    daily_state=None,
    historical_durations=None,
    historical_completion_rates=None,
    model_dir=None,
):
    artifact = _usable_model("duration", task, model_dir)
    if artifact:
        try:
            features = _feature_frame(
                task, daily_state, historical_durations, historical_completion_rates
            )
            predicted = float(artifact["model"].predict(features)[0])
            return round(max(predicted, 15.0), 2), artifact["model_version"]
        except Exception:
            pass
    predicted = predict_duration(task, daily_state, historical_durations)[0]
    return float(predicted), "baseline-v1"


def _completion_with_source(
    task,
    daily_state=None,
    historical_durations=None,
    historical_completion_rates=None,
    model_dir=None,
):
    artifact = _usable_model("completion", task, model_dir)
    if artifact:
        try:
            features = _feature_frame(
                task, daily_state, historical_durations, historical_completion_rates
            )
            probabilities = artifact["model"].predict_proba(features)[0]
            classes = list(artifact["model"].named_steps["model"].classes_)
            positive_index = classes.index(1)
            probability = float(probabilities[positive_index])
            return min(max(probability, 0.0), 1.0), artifact["model_version"]
        except Exception:
            pass
    probability = predict_completion_probability(
        task,
        daily_state,
        historical_completion_rates,
    )
    return min(max(float(probability), 0.0), 1.0), "baseline-v1"


def predict_duration_ml(
    task,
    daily_state=None,
    historical_durations=None,
    historical_completion_rates=None,
    model_dir=None,
):
    return _duration_with_source(
        task,
        daily_state,
        historical_durations,
        historical_completion_rates,
        model_dir,
    )[0]


def predict_completion_probability_ml(
    task,
    daily_state=None,
    historical_durations=None,
    historical_completion_rates=None,
    model_dir=None,
):
    return _completion_with_source(
        task,
        daily_state,
        historical_durations,
        historical_completion_rates,
        model_dir,
    )[0]


def predict_task_ml(
    task,
    daily_state=None,
    historical_durations=None,
    historical_completion_rates=None,
    model_dir=None,
):
    duration, duration_source = _duration_with_source(
        task,
        daily_state,
        historical_durations,
        historical_completion_rates,
        model_dir,
    )
    probability, completion_source = _completion_with_source(
        task,
        daily_state,
        historical_durations,
        historical_completion_rates,
        model_dir,
    )
    source = (
        "ml-rf-v1"
        if duration_source == "ml-rf-v1" and completion_source == "ml-rf-v1"
        else "baseline-v1"
    )
    return {
        "predicted_duration": max(float(duration), 15.0),
        "completion_probability": min(max(float(probability), 0.0), 1.0),
        "model_version": source,
    }