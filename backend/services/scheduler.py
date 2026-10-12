from datetime import datetime, timedelta
from .priority_engine import calculate_priority
from .ml_prediction import predict_task_ml
from .prediction import explain_duration


def generate_schedule(tasks, daily_state=None, goals_by_id=None, available_hours=8.0, start_time="08:00", task_history=None):
    goals_by_id = goals_by_id or {}
    task_history = task_history or {}
    unique_tasks = {}
    for task in tasks:
        task_key = ("task", task.id) if task.id is not None else ("object", id(task))
        unique_tasks.setdefault(task_key, task)
    enriched = []

    for task in unique_tasks.values():
        goal = goals_by_id.get(task.goal_id)
        history = task_history.get(task.id, {})
        durations = history.get("durations") or []
        completion_rates = history.get("completion_rates") or []

        priority, priority_breakdown = calculate_priority(task, daily_state, goal)
        prediction = predict_task_ml(
            task,
            daily_state,
            durations,
            completion_rates,
        )
        predicted_duration = prediction["predicted_duration"]
        probability = prediction["completion_probability"]

        goal_name = goal.name if goal else None
        explanation = (
            explain_duration(task, daily_state, durations)
            if prediction["model_version"] == "baseline-v1"
            else f"Random Forest ({prediction['model_version']}) prediction: {predicted_duration:.0f}m"
        )
        reason_parts = [
            f"priority {priority:.1f}",
            f"goal {goal_name}" if goal_name else "no linked goal",
            priority_breakdown["urgency_label"],
        ]

        enriched.append({
            "task_id": task.id,
            "title": task.title,
            "priority": priority,
            "estimated_duration": task.estimated_duration,
            "predicted_duration": predicted_duration,
            "completion_probability": probability,
            "model_version": prediction["model_version"],
            "difficulty": task.difficulty,
            "importance": task.importance,
            "deadline": task.deadline,
            "goal_id": goal.id if goal else None,
            "goal_name": goal_name,
            "goal_importance": goal.importance if goal else None,
            "duration_explanation": explanation,
            "priority_explanation": " · ".join(reason_parts),
            "priority_breakdown": priority_breakdown,
        })

    # Greedy multi-objective ordering: priority is the primary objective,
    # while completion probability acts as a tie-breaker.
    enriched.sort(key=lambda x: (x["priority"], x["completion_probability"]), reverse=True)

    current_time = datetime.strptime(start_time, "%H:%M")
    available_minutes = max(float(available_hours), 0) * 60
    used_minutes = 0.0
    result = []

    for item in enriched:
        duration = float(item["predicted_duration"])
        if used_minutes + duration > available_minutes:
            result.append({
                **item,
                "scheduled": False,
                "scheduled_start": None,
                "scheduled_end": None,
                "reason": "Capacity limit reached; task remains pending"
            })
            continue

        start = current_time
        end = start + timedelta(minutes=duration)
        result.append({
            **item,
            "scheduled": True,
            "scheduled_start": start.strftime("%H:%M"),
            "scheduled_end": end.strftime("%H:%M"),
            "reason": None
        })
        current_time = end
        used_minutes += duration

    return result
