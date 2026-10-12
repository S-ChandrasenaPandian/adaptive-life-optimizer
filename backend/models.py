from datetime import datetime, date

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Text
)

from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)

    available_hours = Column(Float, default=8.0)
    normal_sleep_hours = Column(Float, default=8.0)
    preferred_start_time = Column(String, default="08:00")

    created_at = Column(DateTime, default=datetime.utcnow)

    goals = relationship("Goal", back_populates="user")
    tasks = relationship("Task", back_populates="user")
    daily_states = relationship("DailyState", back_populates="user")


class Goal(Base):
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    name = Column(String, nullable=False)
    category = Column(String, nullable=False)

    importance = Column(Integer, default=5)
    target_date = Column(Date, nullable=True)
    progress = Column(Float, default=0.0)

    user = relationship("User", back_populates="goals")
    tasks = relationship("Task", back_populates="goal")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    goal_id = Column(Integer, ForeignKey("goals.id"), nullable=True)

    title = Column(String, nullable=False)
    category = Column(String, nullable=False)

    difficulty = Column(Integer, default=5)
    importance = Column(Integer, default=5)

    deadline = Column(DateTime, nullable=True)

    estimated_duration = Column(Float, nullable=True)

    status = Column(String, default="pending")

    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="tasks")
    goal = relationship("Goal", back_populates="tasks")

    predictions = relationship("Prediction", back_populates="task")
    sessions = relationship("TaskSession", back_populates="task")


class DailyState(Base):
    __tablename__ = "daily_states"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    date = Column(Date, default=date.today)
    available_hours = Column(Float, nullable=True)

    sleep_hours = Column(Float, nullable=True)
    energy = Column(Float, nullable=True)
    focus = Column(Float, nullable=True)
    workload = Column(Float, nullable=True)
    exercise_minutes = Column(Float, nullable=True)

    user = relationship("User", back_populates="daily_states")


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)

    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)

    predicted_duration = Column(Float, nullable=True)
    completion_probability = Column(Float, nullable=True)

    prediction_time = Column(DateTime, default=datetime.utcnow)

    model_version = Column(String, default="baseline-v1")

    task = relationship("Task", back_populates="predictions")


class TaskSession(Base):
    __tablename__ = "task_sessions"

    id = Column(Integer, primary_key=True, index=True)

    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)

    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)

    actual_duration = Column(Float, nullable=True)

    task = relationship("Task", back_populates="sessions")
    outcome = relationship(
        "Outcome",
        back_populates="task_session",
        uselist=False
    )


class Outcome(Base):
    __tablename__ = "outcomes"

    id = Column(Integer, primary_key=True, index=True)

    task_session_id = Column(
        Integer,
        ForeignKey("task_sessions.id"),
        nullable=False
    )

    completed = Column(Boolean, default=False)

    actual_duration = Column(Float, nullable=True)

    user_rating = Column(Float, nullable=True)

    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    task_session = relationship(
        "TaskSession",
        back_populates="outcome"
    )