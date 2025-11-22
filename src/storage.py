import json
from pathlib import Path
from threading import Lock
from typing import Any, Dict


class JsonStore:
    def __init__(self, path: Path, default_payload: Dict[str, Any]):
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._default = default_payload
        if not self._path.exists():
            self._write(self._default)

    def _read_unlocked(self) -> Dict[str, Any]:
        with self._path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _write(self, payload: Dict[str, Any]) -> None:
        with self._path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    def load(self) -> Dict[str, Any]:
        with self._lock:
            return self._read_unlocked()

    def persist(self, payload: Dict[str, Any]) -> None:
        with self._lock:
            self._write(payload)

    def update(self, mutator: Any) -> Dict[str, Any]:
        """
        Atomically apply a mutator function that receives the current payload and must return
        the new payload. The updated payload is persisted and returned.
        """
        with self._lock:
            payload = self._read_unlocked()
            new_payload = mutator(payload)
            self._write(new_payload)
            return new_payload

