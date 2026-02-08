from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

API_BASE = "https://slack.com/api"


class SlackClient:
    """Async wrapper around the Slack Web API."""

    def __init__(self, bot_token: str) -> None:
        self._http = httpx.AsyncClient(
            base_url=API_BASE,
            headers={
                "Authorization": f"Bearer {bot_token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            timeout=15.0,
        )

    async def _post(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        resp = await self._http.post(f"/{method}", json=payload)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Slack API error ({method}): {data.get('error', 'unknown')}")
        return data

    async def post_message(self, channel: str, text: str, thread_ts: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"channel": channel, "text": text}
        if thread_ts:
            payload["thread_ts"] = thread_ts
        return await self._post("chat.postMessage", payload)

    async def post_blocks(
        self, channel: str, blocks: list[dict[str, Any]], text: str = "", thread_ts: str | None = None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"channel": channel, "blocks": blocks, "text": text}
        if thread_ts:
            payload["thread_ts"] = thread_ts
        return await self._post("chat.postMessage", payload)

    async def add_reaction(self, channel: str, timestamp: str, emoji: str) -> dict[str, Any]:
        return await self._post("reactions.add", {"channel": channel, "timestamp": timestamp, "name": emoji})

    async def get_channel_history(self, channel: str, limit: int = 10) -> list[dict[str, Any]]:
        data = await self._post("conversations.history", {"channel": channel, "limit": limit})
        return data.get("messages", [])

    async def close(self) -> None:
        await self._http.aclose()
