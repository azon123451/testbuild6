from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import BigInteger, Column, DateTime, Enum, ForeignKey, Integer, Text, create_engine, select
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from shared.enums import MessageSender, SessionStatus

Base = declarative_base()


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    client_telegram_id = Column(BigInteger, index=True, nullable=False)
    operator_telegram_id = Column(BigInteger, nullable=True)
    status = Column(Enum(SessionStatus), default=SessionStatus.ACTIVE, nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    closed_at = Column(DateTime, nullable=True)

    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    sender = Column(Enum(MessageSender), nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    client_telegram_id = Column(BigInteger, index=True, nullable=False)
    operator_telegram_id = Column(BigInteger, nullable=True)

    session = relationship("ChatSession", back_populates="messages")


class Storage:
    """
    Lightweight persistence layer used directly by the bot.
    """

    def __init__(self, database_url: str):
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self.engine = create_engine(database_url, connect_args=connect_args, future=True)
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

    def _get_or_create_session(self, db, client_id: int, operator_id: Optional[int]) -> ChatSession:
        stmt = (
            select(ChatSession)
            .where(ChatSession.client_telegram_id == client_id)
            .where(ChatSession.status == SessionStatus.ACTIVE)
        )
        session = db.scalar(stmt)
        if session:
            if operator_id and not session.operator_telegram_id:
                session.operator_telegram_id = operator_id
                db.commit()
            return session

        session = ChatSession(
            client_telegram_id=client_id,
            operator_telegram_id=operator_id,
            status=SessionStatus.ACTIVE,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    def log_message(self, client_id: int, operator_id: Optional[int], sender: MessageSender, text: str) -> None:
        with self.SessionLocal() as db:
            session = self._get_or_create_session(db, client_id, operator_id)
            message = Message(
                session_id=session.id,
                sender=sender,
                text=text,
                client_telegram_id=client_id,
                operator_telegram_id=operator_id,
            )
            db.add(message)
            db.commit()

    def close_session(self, client_id: int) -> None:
        with self.SessionLocal() as db:
            stmt = (
                select(ChatSession)
                .where(ChatSession.client_telegram_id == client_id)
                .where(ChatSession.status == SessionStatus.ACTIVE)
            )
            session = db.scalar(stmt)
            if not session:
                return
            session.status = SessionStatus.CLOSED
            session.closed_at = datetime.utcnow()
            db.commit()

    def get_history(self, client_id: int, limit: int) -> List[Message]:
        with self.SessionLocal() as db:
            stmt = (
                select(Message)
                .where(Message.client_telegram_id == client_id)
                .order_by(Message.created_at.desc())
                .limit(limit)
            )
            rows = db.scalars(stmt).all()
            return list(reversed(rows))

