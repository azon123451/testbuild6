from typing import Any, Dict

import httpx

from shared.schemas import MessageCreate


class HistoryClient:
    def __init__(self, base_url: str, token: str):
        self._base_url = base_url.rstrip("/")
        self._headers = {"X-Bot-Token": token}
        self._client = httpx.AsyncClient(base_url=self._base_url, headers=self._headers, timeout=10.0)

    async def log_message(self, payload: MessageCreate) -> Dict[str, Any]:
        response = await self._client.post("/internal/messages", json=payload.model_dump())
        response.raise_for_status()
        return response.json()

    async def close_session(self, client_id: int) -> None:
        response = await self._client.post(f"/internal/sessions/{client_id}/close")
        response.raise_for_status()

    async def aclose(self):
        await self._client.aclose()

