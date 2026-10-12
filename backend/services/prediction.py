from statistics import mean


def _state_factors(daily_state):
    factors = []
    if not daily_state:
        return factors

    if daily_state.sleep_hours is not None:
        if daily_state.sleep_hours < 6:
            factors.append(("sleep < 6h", 1.20))
        elif daily_state.sleep_hours < 7:
            factors.append(("sleep < 7h", 1.10))
        elif daily_state.sleep_hours >= 8:
            factors.append(("sleep ≥ 8h", 0.95))

    if daily_state.energy is not None:
        if daily_state.energy <= 3:
            factors.append(("low energy", 1.25))
        elif daily_state.energy <= 5:
            factors.append(("moderate-low energy", 1.10))
        elif daily_state.energy >= 8:
            factors.append(("high energy", 0.90))

    if daily_state.focus is not None:
        if daily_state.focus <= 3:
            factors.append(("low focus", 1.15))
        elif daily_state.focus <= 5:
            factors.append(("moderate-low focus", 1.08))
        elif daily_state.focus >= 8:
            factors.append(("high focus", 0.95))

    if daily_state.workload is not None:
        if daily_state.workload >= 8:
            factors.append(("high workload", 1.15))
        elif daily_state.workload >= 6:
            factors.append(("elevated workload", 1.08))
        elif daily_state.workload <= 3:
            factors.append(("low workload", 0.97))

    if daily_state.exercise_minutes is not None and daily_state.exercise_minutes >= 30:
        factors.append(("exercise ≥ 30m", 0.97))
    return factors


def predict_duration(task, daily_state=None, historical_durations=None):
    estimate = float(task.estimated_duration or 60)
    if historical_durations:
        historical_average = mean(historical_durations)
        base = historical_average * 0.70 + estimate * 0.30
        base_method = "history-adjusted"
    else:
        difficulty_factor = 1 + ((float(task.difficulty or 5) - 5) * 0.05)
        base = estimate * difficulty_factor
        base_method = "difficulty-adjusted estimate"

    state_factor = 1.0
    for _, multiplier in _state_factors(daily_state):
        state_factor *= multiplier

    return round(max(base * state_factor, 15), 2), base_method, base


def explain_duration(task, daily_state=None, historical_durations=None):
    predicted, method, base = predict_duration(task, daily_state, historical_durations)
    estimate = float(task.estimated_duration or 60)
    factors = _state_factors(daily_state)
    if historical_durations:
        history_avg = mean(historical_durations)
        base_text = f"{estimate:.0f}m estimate blended with {history_avg:.0f}m historical average (70/30)"
    else:
        difficulty_factor = 1 + ((float(task.difficulty or 5) - 5) * 0.05)
        base_text = f"{estimate:.0f}m estimate × difficulty factor {difficulty_factor:.2f}"
    factor_text = " · ".join(f"{name} ×{multiplier:.2f}" for name, multiplier in factors)
    if factor_text:
        return f"{base_text} · {factor_text} = {predicted:.0f}m"
    return f"{base_text} = {predicted:.0f}m"


def predict_completion_probability(task, daily_state=None, historical_completion_rates=None):
    if historical_completion_rates:
        probability = mean(historical_completion_rates) * 0.70 + 0.70 * 0.30
    else:
        probability = 0.70
        probability += (float(task.importance or 5) - 5) * 0.02
        probability -= (float(task.difficulty or 5) - 5) * 0.025

        if daily_state:
            if daily_state.sleep_hours is not None:
                if daily_state.sleep_hours < 6:
                    probability -= 0.08
                elif daily_state.sleep_hours < 7:
                    probability -= 0.04
                elif daily_state.sleep_hours >= 8:
                    probability += 0.04
            if daily_state.energy is not None:
                probability += (daily_state.energy - 5) * 0.03
            if daily_state.focus is not None:
                probability += (daily_state.focus - 5) * 0.025
            if daily_state.workload is not None:
                probability -= (daily_state.workload - 5) * 0.02
            if daily_state.exercise_minutes is not None and daily_state.exercise_minutes >= 30:
                probability += 0.02

    return round(max(0.10, min(probability, 0.95)), 2)
