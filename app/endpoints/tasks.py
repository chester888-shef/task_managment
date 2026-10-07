from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy import select, func, or_, case
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.endpoints.deps import get_current_user
from app.models.task import Task
from app.models.user import User
from app.models.enums import TaskStatus, TaskPriority
from app.schemas.task import TaskCreate, TaskUpdate, TaskRead as TaskResponse

router = APIRouter(prefix="/tasks", tags=["tasks"])


class StatusUpdate(BaseModel):
    status: TaskStatus


async def check_active_tasks_limit(session: AsyncSession, assignee_id: int):
    active_statuses = [TaskStatus.BACKLOG, TaskStatus.IN_PROGRESS, TaskStatus.REVIEW]
    result = await session.execute(
        select(func.count(Task.id))
        .where(Task.assignee_id == assignee_id)
        .where(Task.status.in_(active_statuses))
    )
    count = result.scalar() or 0
    if count >= 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has 10 active tasks."
        )


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_in: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if task_in.assignee_id:
        await check_active_tasks_limit(db, task_in.assignee_id)

    new_task = Task(
        **task_in.model_dump(),
        author_id=current_user.id,
        status=TaskStatus.BACKLOG,
    )
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)
    return new_task


@router.get("/", response_model=List[TaskResponse])
async def get_tasks(
    search: Optional[str] = Query(None, description="Search in title and description"),
    status: Optional[TaskStatus] = None,
    priority: Optional[TaskPriority] = None,
    assignee_id: Optional[int] = None,
    deadline_before: Optional[datetime] = None,
    sort_by: Optional[str] = Query(None, pattern="^(created_at|deadline|priority)$"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Task)
    if search:
        query = query.where(
            or_(
                Task.title.ilike(f"%{search}%"),
                Task.description.ilike(f"%{search}%"),
            )
        )

    if status:
        query = query.where(Task.status == status)
    if priority:
        query = query.where(Task.priority == priority)
    if assignee_id:
        query = query.where(Task.assignee_id == assignee_id)
    if deadline_before:
        query = query.where(Task.deadline <= deadline_before)

    priority_order = case(
        (Task.priority == TaskPriority.HIGH, 1),
        (Task.priority == TaskPriority.MEDIUM, 2),
        (Task.priority == TaskPriority.LOW, 3),
        else_=4,
    )

    if sort_by == "created_at":
        col = Task.created_at.desc() if sort_order == "desc" else Task.created_at.asc()
        query = query.order_by(col)
    elif sort_by == "deadline":
        col = Task.deadline.desc().nulls_last() if sort_order == "desc" else Task.deadline.asc().nulls_last()
        query = query.order_by(col)
    elif sort_by == "priority":
        col = priority_order.desc() if sort_order == "desc" else priority_order.asc()
        query = query.order_by(col)
    else:
        # Дефолтне сортування: High -> Medium -> Low, а потім найближчий дедлайн
        query = query.order_by(priority_order.asc(), Task.deadline.asc().nulls_last())


    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/overdue", response_model=List[TaskResponse])
async def get_overdue_tasks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    query = select(Task).where(
        Task.deadline.is_not(None),
        Task.deadline < now,
        Task.status.not_in([TaskStatus.DONE, TaskStatus.CANCELLED]),
    )
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/stats")
async def get_tasks_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    active_statuses = [TaskStatus.BACKLOG, TaskStatus.IN_PROGRESS, TaskStatus.REVIEW]

    total = await db.scalar(select(func.count(Task.id)))

    status_rows = (await db.execute(
        select(Task.status, func.count(Task.id)).group_by(Task.status)
    )).all()
    by_status = {s.value: 0 for s in TaskStatus}
    for s, count in status_rows:
        by_status[s.value] = count

    priority_rows = (await db.execute(
        select(Task.priority, func.count(Task.id)).group_by(Task.priority)
    )).all()
    by_priority = {p.value: 0 for p in TaskPriority}
    for p, count in priority_rows:
        by_priority[p.value] = count

    overdue = await db.scalar(
        select(func.count(Task.id)).where(
            Task.deadline.is_not(None),
            Task.deadline < now,
            Task.status.not_in([TaskStatus.DONE, TaskStatus.CANCELLED]),
        )
    )

    active = await db.scalar(
        select(func.count(Task.id)).where(Task.status.in_(active_statuses))
    )

    return {
        "total_tasks": total or 0,
        "by_status": by_status,
        "by_priority": by_priority,
        "overdue_tasks": overdue or 0,
        "active_tasks": active or 0,
    }


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status in [TaskStatus.DONE, TaskStatus.CANCELLED]:
        raise HTTPException(status_code=400, detail="Cannot edit Done or Cancelled tasks")

    update_data = task_update.model_dump(exclude_unset=True)

    if "assignee_id" in update_data:
        if task.status in [TaskStatus.REVIEW, TaskStatus.DONE]:
            raise HTTPException(status_code=400, detail="Cannot change assignee in Review or Done status")

        new_assignee = update_data["assignee_id"]
        if new_assignee and new_assignee != task.assignee_id:
            await check_active_tasks_limit(db, new_assignee)

    for field, value in update_data.items():
        setattr(task, field, value)

    await db.commit()
    await db.refresh(task)
    return task


@router.patch("/{task_id}/status", response_model=TaskResponse)
async def change_task_status(
    task_id: int,
    status_update: StatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    new_status = status_update.status
    current_status = task.status

    if current_status == new_status:
        return task

    allowed_transitions = {
        TaskStatus.BACKLOG: [TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED],
        TaskStatus.IN_PROGRESS: [TaskStatus.REVIEW, TaskStatus.CANCELLED],
        TaskStatus.REVIEW: [TaskStatus.DONE, TaskStatus.CANCELLED],
    }

    if current_status in [TaskStatus.DONE, TaskStatus.CANCELLED]:
        raise HTTPException(status_code=400, detail="Cannot change status from Done or Cancelled")

    if new_status not in allowed_transitions.get(current_status, []):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transition from {current_status.value} to {new_status.value}",
        )

    if new_status == TaskStatus.DONE:
        if not task.assignee_id:
            raise HTTPException(status_code=400, detail="Cannot mark as Done without an assignee")

        if task.deadline and task.deadline < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Cannot mark as Done. Deadline has passed.")

    task.status = new_status
    await db.commit()
    await db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status in [TaskStatus.IN_PROGRESS, TaskStatus.REVIEW]:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete tasks in progress or review. Change status to Cancelled or Done first.",
        )

    await db.delete(task)
    await db.commit()
    return None
