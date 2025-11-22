from typing import Dict, Optional, Set


class SessionRegistry:
    def __init__(self):
        self.client_to_operator: Dict[int, int] = {}
        self.operator_to_clients: Dict[int, Set[int]] = {}
        self.operator_active_client: Dict[int, int] = {}

    def bind(self, client_id: int, operator_id: int):
        self.client_to_operator[client_id] = operator_id
        self.operator_to_clients.setdefault(operator_id, set()).add(client_id)
        self.operator_active_client[operator_id] = client_id

    def release(self, client_id: int) -> Optional[int]:
        operator_id = self.client_to_operator.pop(client_id, None)
        if operator_id is None:
            return None
        clients = self.operator_to_clients.get(operator_id)
        if clients:
            clients.discard(client_id)
            if not clients:
                self.operator_to_clients.pop(operator_id, None)
        active = self.operator_active_client.get(operator_id)
        if active == client_id:
            self.operator_active_client.pop(operator_id, None)
        return operator_id

    def get_operator(self, client_id: int) -> Optional[int]:
        return self.client_to_operator.get(client_id)

    def get_active_client(self, operator_id: int) -> Optional[int]:
        return self.operator_active_client.get(operator_id)

    def set_active_client(self, operator_id: int, client_id: int) -> bool:
        if client_id not in self.client_to_operator:
            return False
        if self.client_to_operator[client_id] != operator_id:
            return False
        self.operator_active_client[operator_id] = client_id
        return True

    def get_clients_for_operator(self, operator_id: int) -> Set[int]:
        return self.operator_to_clients.get(operator_id, set())

