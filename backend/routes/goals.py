from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Goal, Task
from ..schemas import GoalCreate, GoalResponse

router = APIRouter(prefix="/goals", tags=["Goals"])


def _progress(db, goal):
    tasks = db.query(Task).filter(
        Task.goal_id == goal.id,
        Task.status != "deleted",
    ).all()
    if not tasks:
        return float(goal.progress or 0)
    weights = [max(1, int(t.importance or 5) * int(t.difficulty or 5)) for t in tasks]
    completed = [w for t, w in zip(tasks, weights) if t.status == "completed"]
    return round((sum(completed) / sum(weights)) * 100, 1) if weights else 0.0


@router.post("/", response_model=GoalResponse)
def create_goal(goal_data: GoalCreate, db: Session = Depends(get_db)):
    target_date = date.fromisoformat(goal_data.target_date) if goal_data.target_date else None
    goal = Goal(
        user_id=goal_data.user_id,
        name=goal_data.name,
        category=goal_data.category,
        importance=goal_data.importance,
        target_date=target_date,
        progress=goal_data.progress,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


@router.get("/", response_model=list[GoalResponse])
def get_goals(db: Session = Depends(get_db)):
    goals = db.query(Goal).all()
    for goal in goals:
        goal.progress = _progress(db, goal)
    return goals


@router.get("/user/{user_id}/summary")
def get_goal_summary(user_id: int, db: Session = Depends(get_db)):
    goals = db.query(Goal).filter(Goal.user_id == user_id).all()
    result = []
    for goal in goals:
        tasks = db.query(Task).filter(
            Task.goal_id == goal.id,
            Task.status != "deleted",
        ).all()
        progress = _progress(db, goal)
        result.append({
            "id": goal.id,
            "name": goal.name,
            "category": goal.category,
            "importance": goal.importance,
            "target_date": goal.target_date,
            "progress": progress,
            "task_count": len(tasks),
            "completed_tasks": sum(1 for t in tasks if t.status == "completed"),
            "pending_tasks": sum(1 for t in tasks if t.status == "pending"),
            "linked_tasks": [
                {"id": t.id, "title": t.title, "status": t.status, "importance": t.importance, "difficulty": t.difficulty}
                for t in tasks
            ],
        })
    return result
