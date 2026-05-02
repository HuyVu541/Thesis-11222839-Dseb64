from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class SessionCreate(BaseModel):
    id: str
    title: Optional[str] = "New Conversation"


class SessionResponse(BaseModel):
    id: str
    title: Optional[str] = "New Conversation"
    created_at: datetime

    class Config:
        from_attributes = True
