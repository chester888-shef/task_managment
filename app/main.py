import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI
from sqlalchemy import update
from app.core.database import SessionLocal
from app.endpoints import auth, tasks, comments
from app.models.enums import TaskStatus
from app.models.task import Task


async def cancel_overdue_tasks():
    """Разова перевірка і скасування прострочених задач."""
    async with SessionLocal() as session:
        now = datetime.now(timezone.utc)
        stmt = (
            update(Task)
            .where(
                Task.deadline.is_not(None),
                Task.deadline < now,
                Task.status.not_in([TaskStatus.DONE, TaskStatus.CANCELLED]),
            )
            .values(status=TaskStatus.CANCELLED)
        )
        await session.execute(stmt)
        await session.commit()


async def periodic_overdue_checker(interval_seconds: int = 60):
    """Фоновий цикл, який періодично викликає cancel_overdue_tasks."""
    while True:
        try:
            await cancel_overdue_tasks()
        except Exception as e:
            print(f"Error in background task: {e}")
        await asyncio.sleep(interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Запускаємо періодичну фонову задачу при старті сервера
    bg_task = asyncio.create_task(periodic_overdue_checker(60))
    yield
    # При зупинці сервера коректно скасовуємо фонову задачу
    bg_task.cancel()


app = FastAPI(title="Task Management API", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(comments.router)


@app.get("/health")
async def health():
    return {"status": "ok"}