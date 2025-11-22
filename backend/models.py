from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declarative_base, relationship

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

    messages = relationship("Message", back_populates="session", cascade="all,delete-orphan")


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

