from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class CommentCreate(BaseModel):
    text: str = Field(min_length=5)

class CommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    task_id: int
    author_id: int
    created_at: datetime