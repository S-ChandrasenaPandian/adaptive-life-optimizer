import os
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import DailyState, Goal, Task, Prediction, User

router = APIRouter(prefix="/assistant", tags=["Assistant"])

class AssistantRequest(BaseModel):
    question: str


def local_answer(question, user, goals, tasks, state):
    q = question.lower()
    pending = [t for t in tasks if t.status == "pending"]
    if "why" in q and ("plan" in q or "schedule" in q):
        top = sorted(pending, key=lambda t: (t.importance or 5, t.difficulty or 5), reverse=True)[:2]
        names = ", ".join(t.title for t in top) or "your current tasks"
        return f"APLO prioritizes {names} using task importance, difficulty, deadlines, linked-goal importance and today's life state. Re-optimization recalculates these inputs instead of moving tasks randomly."
    if "duration" in q or "long" in q:
        return "Predicted duration starts from your estimate, adjusts for difficulty and today's state, then blends toward your historical durations when outcome data exists."
    if "goal" in q or "progress" in q:
        return "Goals provide optimization context. Linked tasks inherit goal importance and deadline context, while completed linked tasks contribute to the goal progress shown in the Goals view."
    if "adaptive" in q or "learn" in q:
        return "APLO learns from recorded outcomes: actual duration influences future duration estimates and completion outcomes influence future completion probability. Early predictions remain baseline-heavy until enough history exists."
    if "today" in q or "state" in q:
        if state:
            return f"Today's state is sleep {state.sleep_hours}h, energy {state.energy}/10, focus {state.focus}/10, workload {state.workload}/10 and exercise {state.exercise_minutes}m. These inputs affect prediction and priority."
        return "No life-state record has been saved for today yet."
    return f"You have {len(pending)} pending task(s) across {len(goals)} goal(s). Ask me about the plan, prediction logic, goal progress, today's state, or how APLO learns from outcomes."

@router.post("/{user_id}")
def ask_assistant(user_id: int, payload: AssistantRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(id=user_id).first()
    goals = db.query(Goal).filter(Goal.user_id == user_id).all()
    tasks = db.query(Task).filter(Task.user_id == user_id).all()
    state = db.query(DailyState).filter(DailyState.user_id == user_id).order_by(DailyState.date.desc()).first()

    # Optional OpenAI integration. The local explanation path keeps the MVP fully usable
    # even when no API key is configured.
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"answer": local_answer(payload.question, user, goals, tasks, state), "mode": "local-grounded"}

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        context = {
            "user": user.name if user else "User",
            "goals": [{"name": g.name, "importance": g.importance, "progress": g.progress} for g in goals],
            "tasks": [{"title": t.title, "status": t.status, "difficulty": t.difficulty, "importance": t.importance} for t in tasks],
            "today": {"sleep": state.sleep_hours, "energy": state.energy, "focus": state.focus, "workload": state.workload} if state else None,
        }
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
            input=[
                {"role": "system", "content": "You are APLO's explanation layer. Explain the provided system data concisely. Do not invent metrics or claim to have changed the schedule."},
                {"role": "user", "content": f"System data: {context}\nQuestion: {payload.question}"},
            ],
        )
        return {"answer": response.output_text, "mode": "llm-grounded"}
    except Exception:
        return {"answer": local_answer(payload.question, user, goals, tasks, state), "mode": "local-fallback"}
