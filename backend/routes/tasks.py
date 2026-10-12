from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Goal, Task
from ..schemas import TaskCreate, TaskResponse


router = APIRouter(
    prefix="/tasks",
    tags=["Tasks"]
)


@router.post("/", response_model=TaskResponse)
def create_task(
    task_data: TaskCreate,
    db: Session = Depends(get_db)
):
    if task_data.goal_id is not None:
        goal = db.query(Goal).filter(
            Goal.id == task_data.goal_id,
            Goal.user_id == task_data.user_id,
        ).first()
        if goal is None:
            raise HTTPException(status_code=404, detail="Goal not found")

    task = Task(
        user_id=task_data.user_id,
        goal_id=task_data.goal_id,
        title=task_data.title,
        category=task_data.category,
        difficulty=task_data.difficulty,
        importance=task_data.importance,
        deadline=task_data.deadline,
        estimated_duration=task_data.estimated_duration
    )

    db.add(task)
    db.commit()
    db.refresh(task)

    return task


@router.get("/", response_model=list[TaskResponse])
def get_tasks(db: Session = Depends(get_db)):
    return db.query(Task).filter(Task.status != "deleted").all()


@router.delete("/{task_id}")
def delete_task(
    task_id: int,
    user_id: int,
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task is None or task.user_id != user_id or task.status == "deleted":
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status == "completed":
        raise HTTPException(
            status_code=409,
            detail="Completed tasks cannot be removed because their history is preserved",
        )

    if task.status != "pending":
        raise HTTPException(
            status_code=409,
            detail="Only pending tasks can be removed",
        )

    task.status = "deleted"
    db.commit()
    db.refresh(task)
    return {
        "message": "Task removed from the active task set",
        "task_id": task.id,
        "status": task.status,
    }