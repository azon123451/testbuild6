from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .enums import MessageSender, SessionStatus


class SessionBase(BaseModel):
    client_telegram_id: int = Field(..., ge=1)
    operator_telegram_id: Optional[int] = Field(default=None, ge=1)
    status: SessionStatus = SessionStatus.ACTIVE


class SessionCreate(SessionBase):
    pass


class SessionRead(SessionBase):
    id: int
    started_at: datetime
    closed_at: Optional[datetime] = None


class MessageCreate(BaseModel):
    client_telegram_id: int = Field(..., ge=1)
    operator_telegram_id: Optional[int] = Field(default=None, ge=1)
    sender: MessageSender
    text: str = Field(..., min_length=1, max_length=4096)


class MessageRead(MessageCreate):
    id: int
    session_id: int
    created_at: datetime

