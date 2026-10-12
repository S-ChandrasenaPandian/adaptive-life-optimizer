from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from .database import Base, engine
from . import models
from .routes import users, goals, tasks, daily_state, planner, outcomes, analytics, assistant, ml

Base.metadata.create_all(bind=engine)


def ensure_daily_state_capacity_column():
    """Add the capacity column to an existing database without removing data."""
    inspector = inspect(engine)
    if "daily_states" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("daily_states")}
    if "available_hours" in columns:
        return

    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE daily_states ADD COLUMN available_hours REAL")
        )
        connection.execute(
            text(
                "UPDATE daily_states "
                "SET available_hours = 8.0 "
                "WHERE available_hours IS NULL"
            )
        )


ensure_daily_state_capacity_column()

app = FastAPI(
    title="Adaptive Personal Life Optimization System",
    description="AI-driven personal optimization platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(goals.router)
app.include_router(tasks.router)
app.include_router(daily_state.router)
app.include_router(planner.router)
app.include_router(outcomes.router)
app.include_router(analytics.router)
app.include_router(assistant.router)
app.include_router(ml.router)

@app.get("/")
def root():
    return {"message": "Adaptive Personal Life Optimization System is running", "version": "1.0.0"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "database": "connected", "version": "1.0.0"}
