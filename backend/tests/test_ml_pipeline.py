import tempfile
import unittest
from datetime import date, datetime, time, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.models import DailyState, Goal, Outcome, Prediction, Task, TaskSession, User
from backend.routes.daily_state import save_daily_state
from backend.routes.ml import get_ml_evaluation, get_ml_status, train_user_models
from backend.routes.planner import generate_user_schedule
from backend.routes.tasks import create_task, delete_task, get_tasks
from backend.schemas import DailyStateCreate, TaskCreate
from backend.services.ml_evaluation import evaluate_models
from backend.services.ml_features import FEATURE_NAMES, build_task_features
from backend.services.ml_prediction import (
    predict_completion_probability_ml,
    predict_duration_ml,
    predict_task_ml,
)
from backend.services.ml_training import (
    ARTIFACT_NAMES,
    load_model,
    train_completion_model,
    train_duration_model,
    train_models,
)
from backend.services.scheduler import generate_schedule
from backend.services.prediction import (
    predict_completion_probability,
    predict_duration,
)


class MLPipelineTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.db = self.session_factory()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.model_dir = Path(self.temp_dir.name)
        self._add_history()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()
        self.temp_dir.cleanup()

    def _add_history(self):
        user = User(id=2, name="In-memory demo", available_hours=8)
        self.db.add(user)
        self.db.add(Goal(
            id=1,
            user_id=2,
            name="Test goal",
            category="Academic",
            importance=8,
            progress=0,
        ))
        tasks = [
            Task(id=1, user_id=2, goal_id=1, title="Trees", category="Academic", difficulty=8, importance=9, estimated_duration=90, status="pending"),
            Task(id=2, user_id=2, title="Lists", category="Academic", difficulty=6, importance=7, estimated_duration=60, status="pending"),
            Task(id=3, user_id=2, title="Wellness", category="Health", difficulty=4, importance=6, estimated_duration=45, status="pending"),
        ]
        self.db.add_all(tasks)
        self.db.flush()

        base_date = date.today() - timedelta(days=30)
        for day_index in range(12):
            record_date = base_date + timedelta(days=day_index)
            state = DailyState(
                user_id=2,
                date=record_date,
                available_hours=4.0 + (day_index % 7),
                sleep_hours=5.5 + (day_index % 8) * 0.4,
                energy=4 + (day_index % 6),
                focus=4 + ((day_index * 2) % 6),
                workload=3 + ((day_index * 3) % 7),
                exercise_minutes=(day_index * 5) % 61,
            )
            self.db.add(state)
            for slot in range(2):
                task = tasks[(day_index + slot) % len(tasks)]
                start = datetime.combine(record_date, time(8 + slot * 3, 0))
                duration = float(task.estimated_duration + ((day_index * 17 + task.id * 11) % 43) - 20)
                session = TaskSession(
                    task_id=task.id,
                    start_time=start,
                    end_time=start + timedelta(minutes=duration),
                    actual_duration=duration,
                )
                self.db.add(session)
                self.db.flush()
                self.db.add(Outcome(
                    task_session_id=session.id,
                    completed=((day_index + task.id) % 4 != 0),
                    actual_duration=duration,
                    created_at=start + timedelta(minutes=duration),
                    notes="isolated unittest fixture",
                ))
        self.db.commit()

    def test_feature_generation_has_required_fields(self):
        task = SimpleNamespace(
            difficulty=8,
            importance=9,
            estimated_duration=90,
            category="Academic",
        )
        state = SimpleNamespace(
            sleep_hours=7,
            energy=8,
            focus=7,
            workload=5,
            exercise_minutes=30,
            available_hours=4,
        )
        features = build_task_features(task, state, [80, 100], [1, 0.5])
        self.assertEqual(list(features), FEATURE_NAMES)
        self.assertEqual(features["historical_average_duration"], 90)
        self.assertEqual(features["historical_completion_rate"], 0.75)
        self.assertEqual(features["category"], "Academic")

    def test_duration_and_completion_models_train(self):
        duration = train_duration_model(self.db, user_id=2, model_dir=self.model_dir)
        completion = train_completion_model(self.db, user_id=2, model_dir=self.model_dir)
        self.assertTrue(duration["trained"])
        self.assertTrue(completion["trained"])
        self.assertIsNotNone(duration["mae"])
        self.assertIsNotNone(completion["accuracy"])
        self.assertTrue((self.model_dir / ARTIFACT_NAMES["duration"]).is_file())
        self.assertTrue((self.model_dir / ARTIFACT_NAMES["completion"]).is_file())

    def test_model_loading_and_predictions(self):
        train_models(self.db, user_id=2, model_dir=self.model_dir)
        self.assertIsNotNone(load_model("duration", self.model_dir))
        self.assertIsNotNone(load_model("completion", self.model_dir))
        task = self.db.query(Task).filter(Task.id == 1).one()
        state = self.db.query(DailyState).order_by(DailyState.date.desc()).first()
        duration = predict_duration_ml(task, state, [90, 100], [1, 0], self.model_dir)
        probability = predict_completion_probability_ml(
            task, state, [90, 100], [1, 0], self.model_dir
        )
        prediction = predict_task_ml(task, state, [90, 100], [1, 0], self.model_dir)
        self.assertGreaterEqual(duration, 15)
        self.assertGreaterEqual(probability, 0)
        self.assertLessEqual(probability, 1)
        self.assertEqual(prediction["model_version"], "ml-rf-v1")

    def test_baseline_fallback_when_artifacts_are_missing(self):
        task = self.db.query(Task).filter(Task.id == 1).one()
        state = self.db.query(DailyState).order_by(DailyState.date.desc()).first()
        expected_duration = predict_duration(task, state, [90])[0]
        expected_probability = predict_completion_probability(task, state, [0.5])
        self.assertEqual(
            predict_duration_ml(task, state, [90], [0.5], self.model_dir),
            expected_duration,
        )
        self.assertEqual(
            predict_completion_probability_ml(task, state, [90], [0.5], self.model_dir),
            expected_probability,
        )
        self.assertEqual(
            predict_task_ml(task, state, [90], [0.5], self.model_dir)["model_version"],
            "baseline-v1",
        )
        (self.model_dir / ARTIFACT_NAMES["duration"]).write_bytes(b"invalid artifact")
        self.assertEqual(
            predict_duration_ml(task, state, [90], [0.5], self.model_dir),
            expected_duration,
        )

    def test_evaluation_returns_measured_metrics(self):
        result = evaluate_models(self.db, user_id=2)
        self.assertEqual(result["duration_samples"], 24)
        self.assertIsNotNone(result["duration"]["mae"])
        self.assertIsNotNone(result["completion"]["accuracy"])
        self.assertIn("precision", result["completion"])
        self.assertIn("recall", result["completion"])

    def test_training_and_status_api_functions(self):
        with patch("backend.services.ml_training.MODEL_DIR", self.model_dir), patch(
            "backend.routes.ml.MODEL_DIR", self.model_dir
        ):
            trained = train_user_models(2, self.db)
            status = get_ml_status(2)
        self.assertEqual(trained["model_version"], "ml-rf-v1")
        self.assertEqual(trained["duration_samples"], 24)
        self.assertEqual(status["status"], "trained")
        self.assertTrue(status["models_exist"])
        self.assertEqual(status["model_version"], "ml-rf-v1")

    def test_planner_route_keeps_prediction_fields_and_model_source(self):
        with patch("backend.services.ml_training.MODEL_DIR", self.model_dir):
            schedule = generate_user_schedule(2, available_hours=4, db=self.db)
        self.assertTrue(schedule)
        for item in schedule:
            self.assertIn("predicted_duration", item)
            self.assertIn("completion_probability", item)
            self.assertIn("model_version", item)
            self.assertIn(item["model_version"], {"ml-rf-v1", "baseline-v1"})
        linked_item = next(item for item in schedule if item["task_id"] == 1)
        self.assertEqual(linked_item["goal_id"], 1)
        self.assertEqual(linked_item["goal_name"], "Test goal")
        self.assertLessEqual(
            sum(item["predicted_duration"] for item in schedule if item["scheduled"]),
            4 * 60,
        )

    def test_status_api_reports_not_trained_without_artifacts(self):
        with patch("backend.routes.ml.MODEL_DIR", self.model_dir):
            status = get_ml_status(2)
        self.assertEqual(status["status"], "not_trained")
        self.assertFalse(status["models_exist"])
        self.assertEqual(status["model_version"], "not_trained")

    def test_evaluation_endpoint_reports_measured_metrics_and_only_stored_predictions(self):
        outcome = (
            self.db.query(Outcome)
            .join(TaskSession)
            .join(Task)
            .filter(Task.id == 1)
            .order_by(Outcome.created_at.desc())
            .first()
        )
        self.db.add_all([
            Prediction(
                task_id=1,
                predicted_duration=60,
                completion_probability=0.75,
                prediction_time=outcome.created_at - timedelta(minutes=1),
                model_version="ml-rf-v1",
            ),
            Prediction(
                task_id=1,
                predicted_duration=65,
                completion_probability=0.70,
                prediction_time=datetime.now() + timedelta(days=1),
                model_version="ml-rf-v1",
            ),
        ])
        self.db.commit()
        train_models(self.db, user_id=2, model_dir=self.model_dir)

        with patch("backend.services.ml_training.MODEL_DIR", self.model_dir), patch(
            "backend.routes.ml.MODEL_DIR", self.model_dir
        ):
            result = get_ml_evaluation(2, self.db)

        self.assertEqual(result["user_id"], 2)
        self.assertEqual(result["model_version"], "ml-rf-v1")
        self.assertEqual(result["training_samples"], 24)
        self.assertIn("mae", result["duration"])
        self.assertIn("r2", result["duration"])
        for metric in ("accuracy", "precision", "recall", "f1"):
            self.assertIn(metric, result["completion"])
        self.assertIsInstance(result["prediction_history"], list)
        self.assertEqual(len(result["prediction_history"]), 2)

        matched = next(
            row for row in result["prediction_history"]
            if row["actual_duration"] is not None
        )
        self.assertEqual(matched["outcome_id"], outcome.id)
        self.assertEqual(
            matched["duration_error"],
            float(outcome.actual_duration) - matched["predicted_duration"],
        )
        unmatched = next(
            row for row in result["prediction_history"]
            if row["prediction_id"] != matched["prediction_id"]
        )
        self.assertIsNone(unmatched["actual_duration"])
        self.assertIsNone(unmatched["duration_error"])
        self.assertEqual(result["prediction_count"], 2)

    def test_daily_state_post_accepts_date_and_updates_same_day(self):
        record_date = date.today()
        first = DailyStateCreate(
            user_id=2,
            date=record_date,
            available_hours=4,
            sleep_hours=7,
            energy=7,
            focus=7,
            workload=5,
            exercise_minutes=30,
        )
        saved = save_daily_state(first, self.db)
        second = DailyStateCreate(
            user_id=2,
            date=record_date,
            available_hours=3.5,
            sleep_hours=7,
            energy=7,
            focus=7,
            workload=5,
            exercise_minutes=30,
        )
        updated = save_daily_state(second, self.db)
        rows = self.db.query(DailyState).filter(
            DailyState.user_id == 2,
            DailyState.date == record_date,
        ).all()
        self.assertEqual(saved.id, updated.id)
        self.assertEqual(updated.available_hours, 3.5)
        self.assertEqual(len(rows), 1)

    def test_create_task_accepts_goal_and_datetime_local_deadline(self):
        task_data = TaskCreate.model_validate({
            "user_id": 2,
            "goal_id": 1,
            "title": "Fourier Series",
            "category": "Academic",
            "difficulty": 9,
            "importance": 8,
            "estimated_duration": 180,
            "deadline": "2026-10-14T13:00",
        })
        created = create_task(task_data, self.db)
        self.assertEqual(created.user_id, 2)
        self.assertEqual(created.goal_id, 1)
        self.assertEqual(created.difficulty, 9)
        self.assertEqual(created.importance, 8)
        self.assertEqual(created.estimated_duration, 180)
        self.assertEqual(created.deadline, datetime(2026, 10, 14, 13, 0))
        self.assertEqual(created.status, "pending")

    def test_create_task_rejects_goal_owned_by_another_user(self):
        self.db.add(User(id=3, name="Other goal owner", available_hours=8))
        self.db.add(Goal(
            id=2,
            user_id=3,
            name="Other user's goal",
            category="Academic",
            importance=7,
        ))
        self.db.commit()

        task_data = TaskCreate.model_validate({
            "user_id": 2,
            "goal_id": 2,
            "title": "Must not link across users",
            "category": "Academic",
        })
        task_count = self.db.query(Task).count()

        with self.assertRaises(HTTPException) as raised:
            create_task(task_data, self.db)

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(self.db.query(Task).count(), task_count)

    def test_delete_pending_task_marks_deleted_and_preserves_prediction_and_goal(self):
        task = self.db.query(Task).filter(Task.id == 1).one()
        self.db.add(Prediction(
            task_id=task.id,
            predicted_duration=90,
            completion_probability=0.8,
            model_version="ml-rf-v1",
        ))
        self.db.commit()

        result = delete_task(task.id, user_id=2, db=self.db)

        self.assertEqual(result["status"], "deleted")
        self.assertEqual(self.db.query(Task).filter(Task.id == task.id).one().status, "deleted")
        self.assertEqual(self.db.query(Prediction).filter(Prediction.task_id == task.id).count(), 1)
        self.assertIsNotNone(self.db.query(Goal).filter(Goal.id == 1).first())
        self.assertNotIn(task.id, {active_task.id for active_task in get_tasks(self.db)})

    def test_delete_nonexistent_task_returns_404(self):
        with self.assertRaises(HTTPException) as raised:
            delete_task(999, user_id=2, db=self.db)
        self.assertEqual(raised.exception.status_code, 404)

    def test_delete_other_users_task_returns_404(self):
        self.db.add(User(id=3, name="Other in-memory owner", available_hours=8))
        foreign_task = Task(
            id=99,
            user_id=3,
            title="Other user's task",
            category="Academic",
            difficulty=5,
            importance=5,
            estimated_duration=30,
            status="pending",
        )
        self.db.add(foreign_task)
        self.db.commit()

        with self.assertRaises(HTTPException) as raised:
            delete_task(99, user_id=2, db=self.db)
        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(self.db.query(Task).filter(Task.id == 99).one().status, "pending")

    def test_completed_task_cannot_be_deleted(self):
        task = self.db.query(Task).filter(Task.id == 1).one()
        task.status = "completed"
        self.db.commit()
        session_count = self.db.query(TaskSession).filter(TaskSession.task_id == task.id).count()
        outcome_count = (
            self.db.query(Outcome)
            .join(TaskSession)
            .filter(TaskSession.task_id == task.id)
            .count()
        )

        with self.assertRaises(HTTPException) as raised:
            delete_task(task.id, user_id=2, db=self.db)

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(self.db.query(Task).filter(Task.id == task.id).one().status, "completed")
        self.assertEqual(self.db.query(TaskSession).filter(TaskSession.task_id == task.id).count(), session_count)
        self.assertEqual(
            self.db.query(Outcome).join(TaskSession).filter(TaskSession.task_id == task.id).count(),
            outcome_count,
        )

    def test_deleted_pending_task_is_absent_from_generated_schedule(self):
        delete_task(1, user_id=2, db=self.db)
        with patch("backend.services.ml_training.MODEL_DIR", self.model_dir):
            schedule = generate_user_schedule(2, available_hours=8, db=self.db)
        self.assertNotIn(1, {item["task_id"] for item in schedule})

    def test_scheduler_emits_each_task_id_at_most_once(self):
        task = self.db.query(Task).filter(Task.id == 1).one()
        schedule = generate_schedule([task, task], available_hours=8)
        self.assertEqual(
            sum(item["task_id"] == task.id for item in schedule),
            1,
        )


if __name__ == "__main__":
    unittest.main()