from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

class UserCreate(BaseModel):
    name: str
    available_hours: float = 8.0
    normal_sleep_hours: float = 8.0
    preferred_start_time: str = "08:00"

class UserResponse(BaseModel):
    id: int
    name: str
    available_hours: float
    normal_sleep_hours: float
    preferred_start_time: str
    class Config:
        from_attributes = True

class GoalCreate(BaseModel):
    user_id: int
    name: str
    category: str
    importance: int = 5
    target_date: Optional[str] = None
    progress: float = 0.0

class GoalResponse(BaseModel):
    id: int
    user_id: int
    name: str
    category: str
    importance: int
    target_date: Optional[date]
    progress: float
    class Config:
        from_attributes = True

class TaskCreate(BaseModel):
    user_id: int
    goal_id: Optional[int] = None
    title: str
    category: str
    difficulty: int = 5
    importance: int = 5
    deadline: Optional[datetime] = None
    estimated_duration: Optional[float] = None

class TaskResponse(BaseModel):
    id: int
    user_id: int
    goal_id: Optional[int]
    title: str
    category: str
    difficulty: int
    importance: int
    deadline: Optional[datetime]
    estimated_duration: Optional[float]
    status: str
    class Config:
        from_attributes = True

class DailyStateCreate(BaseModel):
    user_id: int
    date_value: Optional[date] = Field(default=None, alias="date")
    available_hours: Optional[float] = None
    sleep_hours: Optional[float] = None
    energy: Optional[float] = None
    focus: Optional[float] = None
    workload: Optional[float] = None
    exercise_minutes: Optional[float] = None

    model_config = ConfigDict(populate_by_name=True)

class DailyStateResponse(BaseModel):
    id: int
    user_id: int
    date: date
    available_hours: Optional[float]
    sleep_hours: Optional[float]
    energy: Optional[float]
    focus: Optional[float]
    workload: Optional[float]
    exercise_minutes: Optional[float]

    class Config:
        from_attributes = True

class ScheduleItemResponse(BaseModel):
    task_id: int
    title: str
    priority: float
    estimated_duration: Optional[float]
    predicted_duration: float
    completion_probability: float
    difficulty: int
    importance: int
    deadline: Optional[datetime]
    scheduled: bool
    scheduled_start: Optional[str]
    scheduled_end: Optional[str]
    reason: Optional[str]
    duration_explanation: Optional[str] = None
    goal_id: Optional[int] = None
    goal_name: Optional[str] = None
    goal_importance: Optional[int] = None
    priority_explanation: Optional[str] = None
    priority_breakdown: Optional[dict] = None
    model_version: Optional[str] = None

class UserUpdate(BaseModel):
    name: Optional[str] = None
    available_hours: Optional[float] = None
    normal_sleep_hours: Optional[float] = None
    preferred_start_time: Optional[str] = None
