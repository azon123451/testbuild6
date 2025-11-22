from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, Set


@dataclass
class OperatorState:
    telegram_id: int
    full_name: str
    pin: str
    max_concurrent: int
    active_clients: Set[int] = field(default_factory=set)
    last_active: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_available(self) -> bool:
        return len(self.active_clients) < self.max_concurrent

    def touch(self) -> None:
        self.last_active = datetime.utcnow()


class OperatorManager:
    def __init__(self, allowed_pins: Set[str], max_concurrent: int):
        self.allowed_pins = allowed_pins
        self.max_concurrent = max_concurrent
        self.operators: Dict[int, OperatorState] = {}
        self.pin_bindings: Dict[str, int] = {}

    def authenticate(self, telegram_id: int, full_name: str, pin: str) -> OperatorState:
        if pin not in self.allowed_pins:
            raise ValueError("Неверный пин")

        existing_operator_id = self.pin_bindings.get(pin)
        if existing_operator_id and existing_operator_id != telegram_id:
            raise ValueError("Пин уже занят другим оператором")

        state = self.operators.get(telegram_id)
        if state:
            state.touch()
            return state

        state = OperatorState(
            telegram_id=telegram_id,
            full_name=full_name,
            pin=pin,
            max_concurrent=self.max_concurrent,
        )
        self.operators[telegram_id] = state
        self.pin_bindings[pin] = telegram_id
        return state

    def is_operator(self, telegram_id: int) -> bool:
        return telegram_id in self.operators

    def get(self, telegram_id: int) -> Optional[OperatorState]:
        return self.operators.get(telegram_id)

    def pick_available(self) -> Optional[OperatorState]:
        available = [op for op in self.operators.values() if op.is_available]
        if not available:
            return None
        available.sort(key=lambda x: (len(x.active_clients), x.last_active))
        winner = available[0]
        winner.touch()
        return winner

    def assign_client(self, operator_id: int, client_id: int) -> None:
        operator = self.operators.get(operator_id)
        if not operator:
            raise ValueError("Оператор не найден")
        operator.active_clients.add(client_id)
        operator.touch()

    def release_client(self, operator_id: int, client_id: int) -> None:
        operator = self.operators.get(operator_id)
        if not operator:
            return
        operator.active_clients.discard(client_id)
        operator.touch()

