from collections import deque
from typing import Deque, Optional, Set


class QueueManager:
    def __init__(self):
        self._queue: Deque[int] = deque()
        self._known: Set[int] = set()

    def enqueue(self, client_id: int) -> None:
        if client_id in self._known:
            return
        self._queue.append(client_id)
        self._known.add(client_id)

    def dequeue(self) -> Optional[int]:
        if not self._queue:
            return None
        client_id = self._queue.popleft()
        self._known.discard(client_id)
        return client_id

    def remove(self, client_id: int) -> None:
        if client_id not in self._known:
            return
        self._known.discard(client_id)
        self._queue = deque([cid for cid in self._queue if cid != client_id])

    def __len__(self) -> int:
        return len(self._queue)

