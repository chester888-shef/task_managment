from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.endpoints.deps import get_current_user
from app.models.comment import Comment
from app.models.task import Task
from app.models.user import User
from app.schemas.comments import CommentCreate, CommentRead

router = APIRouter(prefix="/tasks/{task_id}/comments", tags=["comments"])


@router.post("/", response_model=CommentRead, status_code=status.HTTP_201_CREATED)
async def create_comment(
    task_id: int,
    comment_in: CommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Перевіряємо, чи існує задача
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    new_comment = Comment(
        text=comment_in.text,
        task_id=task_id,
        author_id=current_user.id,
    )
    db.add(new_comment)
    await db.commit()
    await db.refresh(new_comment)
    return new_comment


@router.get("/", response_model=List[CommentRead])
async def get_task_comments(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Task not found")

    comments_res = await db.execute(
        select(Comment)
        .where(Comment.task_id == task_id)
        .order_by(Comment.created_at.asc())
    )
    return comments_res.scalars().all()