from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.enums import SessionStatus
from shared.schemas import MessageCreate, MessageRead, SessionRead

from . import models


def get_or_create_session(db: Session, *, client_id: int, operator_id: Optional[int]) -> models.ChatSession:
    stmt = (
        select(models.ChatSession)
        .where(models.ChatSession.client_telegram_id == client_id)
        .where(models.ChatSession.status == SessionStatus.ACTIVE)
    )
    session = db.scalar(stmt)
    if session:
        if operator_id and not session.operator_telegram_id:
            session.operator_telegram_id = operator_id
            db.commit()
            db.refresh(session)
        return session

    session = models.ChatSession(
        client_telegram_id=client_id,
        operator_telegram_id=operator_id,
        status=SessionStatus.ACTIVE,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def close_session(db: Session, *, client_id: int):
    stmt = (
        select(models.ChatSession)
        .where(models.ChatSession.client_telegram_id == client_id)
        .where(models.ChatSession.status == SessionStatus.ACTIVE)
    )
    session = db.scalar(stmt)
    if not session:
        return
    session.status = SessionStatus.CLOSED
    session.closed_at = datetime.utcnow()
    db.commit()


def create_message(db: Session, payload: MessageCreate) -> MessageRead:
    session = get_or_create_session(
        db, client_id=payload.client_telegram_id, operator_id=payload.operator_telegram_id
    )
    message = models.Message(
        session_id=session.id,
        sender=payload.sender,
        text=payload.text,
        client_telegram_id=payload.client_telegram_id,
        operator_telegram_id=payload.operator_telegram_id,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return MessageRead(
        id=message.id,
        session_id=session.id,
        sender=message.sender,
        text=message.text,
        created_at=message.created_at,
        client_telegram_id=message.client_telegram_id,
        operator_telegram_id=message.operator_telegram_id,
    )


def list_messages(db: Session, client_id: int) -> List[MessageRead]:
    stmt = select(models.Message).where(models.Message.client_telegram_id == client_id).order_by(models.Message.id.asc())
    rows = db.scalars(stmt).all()
    return [
        MessageRead(
            id=row.id,
            session_id=row.session_id,
            sender=row.sender,
            text=row.text,
            created_at=row.created_at,
            client_telegram_id=row.client_telegram_id,
            operator_telegram_id=row.operator_telegram_id,
        )
        for row in rows
    ]


def list_active_sessions(db: Session) -> List[SessionRead]:
    stmt = select(models.ChatSession).where(models.ChatSession.status == SessionStatus.ACTIVE).order_by(
        models.ChatSession.started_at.asc()
    )
    rows = db.scalars(stmt).all()
    return [
        SessionRead(
            id=row.id,
            client_telegram_id=row.client_telegram_id,
            operator_telegram_id=row.operator_telegram_id,
            status=row.status,
            started_at=row.started_at,
            closed_at=row.closed_at,
        )
        for row in rows
    ]

