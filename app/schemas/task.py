from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.models.enums import TaskPriority, TaskStatus

#функція для перевірки коректності дедлайну
def validate_deadline(v: datetime | None) -> datetime | None:
    if v is None:
        return v
    if v.tzinfo is None:
        v = v.replace(tzinfo=timezone.utc)
    if v < datetime.now(timezone.utc):
        raise ValueError("Deadline cannot be in the past")
    return v

#поля які користувач може надсилати при створенні а настпуний клас це для редагування задачі і тому там стоїть = Nоne  
class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    assignee_id: int | None = None
    deadline: datetime | None = None

    _check_deadline = field_validator("deadline")(validate_deadline)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    priority: TaskPriority | None = None
    assignee_id: int | None = None
    deadline: datetime | None = None

    _check_deadline = field_validator("deadline")(validate_deadline)


class TaskStatusUpdate(BaseModel):
    status: TaskStatus

#шаблок того що повретає ервер клієнту 
class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    assignee_id: int | None
    author_id: int
    deadline: datetime | None
    created_at: datetime
    updated_at: datetime


class TaskList(BaseModel):
    items: list[TaskRead]
    total: int
    limit: int
    offset: int