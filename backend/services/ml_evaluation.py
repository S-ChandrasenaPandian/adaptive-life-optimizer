from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    precision_score,
    r2_score,
    recall_score,
)

from .ml_features import FEATURE_NAMES
from .ml_training import (
    MODEL_VERSION,
    _feature_frame,
    _make_pipeline,
    _split_indices,
    collect_training_samples,
)


def evaluate_models(db, user_id=None):
    samples = collect_training_samples(db, user_id)
    result = {
        "model_version": MODEL_VERSION,
        "duration_samples": len(samples),
        "completion_samples": len(samples),
        "feature_names": FEATURE_NAMES.copy(),
        "duration": {"mae": None, "r2": None},
        "completion": {
            "accuracy": None,
            "precision": None,
            "recall": None,
            "f1": None,
        },
    }
    if len(samples) < 8:
        return result

    features = _feature_frame(samples)
    for model_type, target_key in (("duration", "duration"), ("completion", "completed")):
        targets = [sample[target_key] for sample in samples]
        split = _split_indices(targets, model_type)
        if split is None:
            continue
        train_indices, test_indices = split
        estimator = _make_pipeline(model_type)
        estimator.fit(features.iloc[train_indices], [targets[i] for i in train_indices])
        predictions = estimator.predict(features.iloc[test_indices])
        actual = [targets[i] for i in test_indices]
        if model_type == "duration":
            result["duration"] = {
                "mae": float(mean_absolute_error(actual, predictions)),
                "r2": float(r2_score(actual, predictions)) if len(actual) >= 2 else None,
            }
        else:
            result["completion"] = {
                "accuracy": float(accuracy_score(actual, predictions)),
                "precision": float(precision_score(actual, predictions, zero_division=0)),
                "recall": float(recall_score(actual, predictions, zero_division=0)),
                "f1": float(f1_score(actual, predictions, zero_division=0)),
            }
    return result