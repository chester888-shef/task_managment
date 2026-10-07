from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import TaskPriority, TaskStatus


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus, name="task_status"),default=TaskStatus.BACKLOG, index=True,)
    priority: Mapped[TaskPriority] = mapped_column(Enum(TaskPriority, name="task_priority"), default=TaskPriority.MEDIUM, index=True)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

