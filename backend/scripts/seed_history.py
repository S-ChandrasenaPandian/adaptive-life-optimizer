import random
from datetime import date, datetime, time, timedelta

from ..database import SessionLocal
from ..models import DailyState, Outcome, Task, TaskSession, User


USER_ID = 2
SEED_PREFIX = "aplo_seed_history_v1:"
SEED = 20261001


def seed_history():
    db = SessionLocal()
    created_states = 0
    skipped_states = 0
    created_attempts = 0
    skipped_attempts = 0
    rng = random.Random(SEED)

    try:
        user = db.query(User).filter(User.id == USER_ID).first()
        if user is None:
            raise RuntimeError(f"Existing user {USER_ID} was not found; no data seeded.")

        tasks = db.query(Task).filter(Task.user_id == USER_ID).order_by(Task.id).all()
        if not tasks:
            raise RuntimeError(f"User {USER_ID} has no existing tasks; no data seeded.")

        today = date.today()
        daily_values = {}
        for day_offset in range(10, 0, -1):
            record_date = today - timedelta(days=day_offset)
            existing_state = (
                db.query(DailyState)
                .filter(
                    DailyState.user_id == USER_ID,
                    DailyState.date == record_date,
                )
                .first()
            )
            if existing_state:
                skipped_states += 1
                daily_values[record_date] = existing_state
                continue

            state = DailyState(
                user_id=USER_ID,
                date=record_date,
                sleep_hours=round(rng.uniform(5.5, 9.0), 1),
                energy=rng.randint(4, 9),
                focus=rng.randint(4, 9),
                workload=rng.randint(3, 9),
                exercise_minutes=rng.choice([0, 10, 20, 30, 45, 60]),
                available_hours=round(rng.uniform(4.0, 10.0), 1),
            )
            db.add(state)
            daily_values[record_date] = state
            created_states += 1

        existing_markers = {
            outcome.notes
            for outcome in (
                db.query(Outcome)
                .join(TaskSession)
                .join(Task)
                .filter(Task.user_id == USER_ID)
                .all()
            )
            if outcome.notes and outcome.notes.startswith(SEED_PREFIX)
        }

        for day_offset in range(10, 0, -1):
            record_date = today - timedelta(days=day_offset)
            state = daily_values[record_date]
            for slot in range(3):
                task_index = ((10 - day_offset) * 3 + slot) % len(tasks)
                task = tasks[task_index]
                marker = f"{SEED_PREFIX}{record_date.isoformat()}:{task.id}:{slot}"
                if marker in existing_markers:
                    skipped_attempts += 1
                    continue

                estimate = float(task.estimated_duration or 60)
                difficulty_factor = 1 + ((float(task.difficulty or 5) - 5) * 0.045)
                state_factor = 1.0
                state_factor += (7 - float(state.sleep_hours or 7)) * 0.018
                state_factor += (6 - float(state.energy or 6)) * 0.012
                state_factor += (6 - float(state.focus or 6)) * 0.012
                state_factor += (float(state.workload or 5) - 5) * 0.012
                duration = max(
                    15.0,
                    estimate * difficulty_factor * state_factor
                    + rng.gauss(0, max(8.0, estimate * 0.13)),
                )
                duration = round(duration, 1)

                completion_probability = 0.78
                completion_probability += (float(state.sleep_hours or 7) - 7) * 0.018
                completion_probability += (float(state.energy or 6) - 6) * 0.035
                completion_probability += (float(state.focus or 6) - 6) * 0.035
                completion_probability -= (float(state.workload or 5) - 5) * 0.025
                completion_probability -= (float(task.difficulty or 5) - 5) * 0.025
                completion_probability += (float(task.importance or 5) - 5) * 0.01
                completed = rng.random() < min(max(completion_probability, 0.45), 0.96)

                started = datetime.combine(record_date, time(8 + slot * 2, 0))
                session = TaskSession(
                    task_id=task.id,
                    start_time=started,
                    end_time=started + timedelta(minutes=duration),
                    actual_duration=duration,
                )
                db.add(session)
                db.flush()
                db.add(Outcome(
                    task_session_id=session.id,
                    completed=completed,
                    actual_duration=duration,
                    user_rating=round(rng.uniform(2.5, 5.0), 1),
                    notes=marker,
                    created_at=started + timedelta(minutes=duration),
                ))
                existing_markers.add(marker)
                created_attempts += 1

        db.commit()
        return {
            "daily_states_created": created_states,
            "daily_states_skipped": skipped_states,
            "attempts_created": created_attempts,
            "attempts_skipped": skipped_attempts,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    result = seed_history()
    print(
        "Seed history complete: "
        f"daily states created={result['daily_states_created']}, "
        f"skipped={result['daily_states_skipped']}; "
        f"attempts created={result['attempts_created']}, "
        f"skipped={result['attempts_skipped']}"
    )