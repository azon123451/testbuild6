from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from .storage import JsonStore


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class OperatorStatus(str, Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"


@dataclass
class Operator:
    chat_id: int
    username: str
    display_name: str
    status: OperatorStatus
    active_client: Optional[int]
    registered_at: str
    updated_at: str

    def to_dict(self) -> Dict:
        return {
            "chat_id": self.chat_id,
            "username": self.username,
            "display_name": self.display_name,
            "status": self.status.value,
            "active_client": self.active_client,
            "registered_at": self.registered_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: Dict) -> "Operator":
        return cls(
            chat_id=int(payload["chat_id"]),
            username=payload.get("username") or "",
            display_name=payload.get("display_name") or "",
            status=OperatorStatus(payload.get("status", OperatorStatus.OFFLINE.value)),
            active_client=payload.get("active_client"),
            registered_at=payload.get("registered_at", utcnow()),
            updated_at=payload.get("updated_at", utcnow()),
        )


class OperatorManager:
    def __init__(self, store: JsonStore, allowlist: Optional[List[int]] = None):
        self._store = store
        self._allowlist = allowlist or []
        self._state = self._load_state()

    def _load_state(self) -> Dict[str, Dict]:
        payload = self._store.load()
        if "operators" not in payload:
            payload = {"operators": {}}
            self._store.persist(payload)
        return payload

    def _save(self) -> None:
        self._store.persist(self._state)

    def _ensure_allowed(self, chat_id: int) -> bool:
        return not self._allowlist or chat_id in self._allowlist

    def is_operator(self, chat_id: int) -> bool:
        return str(chat_id) in self._state["operators"]

    def upsert_operator(self, chat_id: int, username: str, display_name: str) -> Operator:
        if not self._ensure_allowed(chat_id):
            raise PermissionError("Нельзя регистрировать оператора без разрешения владельца.")

        key = str(chat_id)
        now = utcnow()
        if key in self._state["operators"]:
            operator = Operator.from_dict(self._state["operators"][key])
            operator.username = username
            operator.display_name = display_name
            operator.updated_at = now
        else:
            operator = Operator(
                chat_id=chat_id,
                username=username,
                display_name=display_name or username,
                status=OperatorStatus.AVAILABLE,
                active_client=None,
                registered_at=now,
                updated_at=now,
            )
        self._state["operators"][key] = operator.to_dict()
        self._save()
        return operator

    def set_status(self, chat_id: int, status: OperatorStatus) -> Operator:
        operator = self.get_operator(chat_id)
        operator.status = status
        if status == OperatorStatus.OFFLINE:
            operator.active_client = None
        operator.updated_at = utcnow()
        self._state["operators"][str(chat_id)] = operator.to_dict()
        self._save()
        return operator

    def set_active_client(self, chat_id: int, client_id: Optional[int]) -> Operator:
        operator = self.get_operator(chat_id)
        operator.active_client = client_id
        operator.updated_at = utcnow()
        self._state["operators"][str(chat_id)] = operator.to_dict()
        self._save()
        return operator

    def get_operator(self, chat_id: int) -> Operator:
        key = str(chat_id)
        if key not in self._state["operators"]:
            raise KeyError("Оператор не найден. Сначала выполните регистрацию.")
        return Operator.from_dict(self._state["operators"][key])

    def list_operators(self) -> List[Operator]:
        return [
            Operator.from_dict(payload)
            for payload in self._state["operators"].values()
        ]

    def available_operator_ids(self) -> List[int]:
        return [
            op.chat_id
            for op in self.list_operators()
            if op.status == OperatorStatus.AVAILABLE
        ]


class ConversationManager:
    def __init__(self, store: JsonStore):
        self._store = store
        self._state = self._load_state()

    def _load_state(self) -> Dict[str, Dict]:
        payload = self._store.load()
        if "conversations" not in payload:
            payload = {"conversations": {}}
            self._store.persist(payload)
        return payload

    def _save(self) -> None:
        self._store.persist(self._state)

    def bind_client(self, client_chat_id: int, operator_chat_id: int, client_name: str) -> None:
        key = str(client_chat_id)
        self._state["conversations"][key] = {
            "operator_id": operator_chat_id,
            "client_name": client_name,
            "last_activity": utcnow(),
        }
        self._save()

    def release_client(self, client_chat_id: int) -> None:
        key = str(client_chat_id)
        if key in self._state["conversations"]:
            del self._state["conversations"][key]
            self._save()

    def get_operator_for_client(self, client_chat_id: int) -> Optional[int]:
        record = self._state["conversations"].get(str(client_chat_id))
        if not record:
            return None
        record["last_activity"] = utcnow()
        self._save()
        return int(record["operator_id"])

    def get_clients_for_operator(self, operator_chat_id: int) -> List[int]:
        result = []
        for client_id, record in self._state["conversations"].items():
            if int(record["operator_id"]) == operator_chat_id:
                result.append(int(client_id))
        return result

    def conversation_snapshot(self) -> Dict[str, Dict]:
        return self._state["conversations"].copy()

    def get_client_record(self, client_chat_id: int) -> Optional[Dict]:
        return self._state["conversations"].get(str(client_chat_id))

