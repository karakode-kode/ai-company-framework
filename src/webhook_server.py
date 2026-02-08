from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any, Callable, Coroutine

from fastapi import FastAPI, Header, HTTPException, Request

from src.agents.base_agent import Event

logger = logging.getLogger(__name__)

EventCallback = Callable[[Event], Coroutine[Any, Any, None]]


def create_app(webhook_secret: str, on_event: EventCallback) -> FastAPI:
    """Create a FastAPI application wired to push events into the agent system."""

    app = FastAPI(title="AI Company Webhook Server", version="1.0.0")

    def _verify_signature(payload: bytes, signature: str, secret: str) -> bool:
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(f"sha256={expected}", signature)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/webhooks/linear")
    async def linear_webhook(request: Request) -> dict[str, str]:
        body = await request.json()
        action = body.get("action", "unknown")
        data = body.get("data", {})

        event_map: dict[str, str] = {
            "create": "linear_issue_created",
            "update": "linear_issue_updated",
            "remove": "linear_issue_removed",
        }
        event_kind = event_map.get(action, f"linear_{action}")
        await on_event(Event(kind=event_kind, source="linear", payload=data))
        logger.info("Linear webhook: %s", event_kind)
        return {"received": event_kind}

    @app.post("/webhooks/github")
    async def github_webhook(
        request: Request,
        x_hub_signature_256: str = Header(""),
        x_github_event: str = Header(""),
    ) -> dict[str, str]:
        raw = await request.body()
        if webhook_secret and not _verify_signature(raw, x_hub_signature_256, webhook_secret):
            raise HTTPException(status_code=401, detail="Invalid signature")

        body = await request.json()
        action = body.get("action", "")
        event_kind = f"github_{x_github_event}"
        if action:
            event_kind = f"{event_kind}_{action}"

        await on_event(Event(kind=event_kind, source="github", payload=body))
        logger.info("GitHub webhook: %s", event_kind)
        return {"received": event_kind}

    @app.post("/webhooks/slack")
    async def slack_webhook(request: Request) -> dict[str, Any]:
        body = await request.json()

        # Handle Slack URL verification challenge
        if body.get("type") == "url_verification":
            return {"challenge": body["challenge"]}

        event_data = body.get("event", {})
        event_kind = f"slack_{event_data.get('type', 'unknown')}"
        await on_event(Event(kind=event_kind, source="slack", payload=event_data))
        logger.info("Slack webhook: %s", event_kind)
        return {"ok": True}

    return app
