from statistics import mean


FEATURE_NAMES = [
    "difficulty",
    "importance",
    "estimated_duration",
    "sleep_hours",
    "energy",
    "focus",
    "workload",
    "exercise_minutes",
    "available_hours",
    "historical_average_duration",
    "historical_completion_rate",
    "category",
]


def _value(source, name, default):
    value = getattr(source, name, None) if source is not None else None
    return default if value is None else float(value)


def build_task_features(
    task,
    daily_state=None,
    historical_durations=None,
    historical_completion_rates=None,
):
    historical_durations = historical_durations or []
    historical_completion_rates = historical_completion_rates or []
    estimate = _value(task, "estimated_duration", 60.0)

    return {
        "difficulty": _value(task, "difficulty", 5.0),
        "importance": _value(task, "importance", 5.0),
        "estimated_duration": estimate,
        "sleep_hours": _value(daily_state, "sleep_hours", 7.0),
        "energy": _value(daily_state, "energy", 6.0),
        "focus": _value(daily_state, "focus", 6.0),
        "workload": _value(daily_state, "workload", 5.0),
        "exercise_minutes": _value(daily_state, "exercise_minutes", 0.0),
        "available_hours": _value(daily_state, "available_hours", 8.0),
        "historical_average_duration": (
            float(mean(historical_durations)) if historical_durations else estimate
        ),
        "historical_completion_rate": (
            float(mean(historical_completion_rates))
            if historical_completion_rates
            else 0.7
        ),
        "category": str(getattr(task, "category", None) or "Unknown"),
    }