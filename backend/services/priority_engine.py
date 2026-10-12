from datetime import datetime


def calculate_priority(task, daily_state=None, goal=None):
    """Interpretable priority score used by the planner.

    Higher score means APLO has more reason to place the task earlier.
    Components are intentionally transparent for demo/explanation purposes.
    """
    importance = float(task.importance or 5)
    difficulty = float(task.difficulty or 5)
    goal_importance = float(goal.importance if goal else 5)

    urgency = 0.0
    urgency_label = "no deadline"
    if task.deadline:
        hours = (task.deadline - datetime.now()).total_seconds() / 3600
        if hours <= 0:
            urgency, urgency_label = 14.0, "overdue"
        elif hours <= 24:
            urgency, urgency_label = 12.0, "due within 24h"
        elif hours <= 48:
            urgency, urgency_label = 10.0, "due within 48h"
        elif hours <= 72:
            urgency, urgency_label = 7.0, "due within 72h"
        elif hours <= 168:
            urgency, urgency_label = 4.0, "due within 7d"
        else:
            urgency, urgency_label = 1.0, "later deadline"

    goal_bonus = goal_importance * 0.9 if goal else 0.0
    importance_score = importance * 1.6
    difficulty_score = difficulty * 0.45
    completion_bonus = 0.0
    state_adjustment = 0.0
    state_label = "neutral state"

    if daily_state:
        energy = daily_state.energy
        focus = daily_state.focus
        sleep = daily_state.sleep_hours
        workload = daily_state.workload

        if energy is not None and focus is not None:
            readiness = (float(energy) + float(focus)) / 2
            if readiness >= 8:
                state_adjustment += difficulty * 0.35
                state_label = "high readiness for difficult work"
            elif readiness <= 4:
                state_adjustment -= difficulty * 0.30
                state_label = "low readiness; difficult work penalized"

        if sleep is not None and sleep < 6:
            state_adjustment -= difficulty * 0.25
        if workload is not None and workload >= 8:
            state_adjustment -= difficulty * 0.15

    # A modest completion-aware term prevents the planner from filling the day
    # with tasks that are important on paper but currently unlikely to finish.
    completion_bonus = max(0.0, min(1.0, importance / 10.0)) * 1.5

    score = (
        importance_score
        + difficulty_score
        + urgency
        + goal_bonus
        + completion_bonus
        + state_adjustment
    )

    return round(score, 2), {
        "importance": round(importance_score, 2),
        "goal_importance": round(goal_bonus, 2),
        "urgency": round(urgency, 2),
        "urgency_label": urgency_label,
        "difficulty": round(difficulty_score, 2),
        "state_adjustment": round(state_adjustment, 2),
        "state_label": state_label,
    }
