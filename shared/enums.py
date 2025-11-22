from enum import Enum


class SessionStatus(str, Enum):
    ACTIVE = "active"
    QUEUED = "queued"
    CLOSED = "closed"


class MessageSender(str, Enum):
    CLIENT = "client"
    OPERATOR = "operator"
    BOT = "bot"

