from __future__ import annotations

import logging
from typing import Any

from src.agents.base_agent import BaseAgent, Event, ToolBox

logger = logging.getLogger(__name__)


class ProductManagerAgent(BaseAgent):
    """Converts ideas and feature requests into structured Linear epics and tickets."""

    def __init__(self, tools: ToolBox, config: dict[str, Any]) -> None:
        super().__init__(name="ProductManager", tools=tools, config=config)
        self._team_key: str = config.get("linear_team_key", "ENG")
        self._default_priority: int = config.get("default_priority", 3)
        self._team_id: str | None = None
        self._workflow_states: dict[str, str] = {}

    async def poll(self) -> None:
        """Ensure team metadata is cached on each poll cycle."""
        if self._team_id is None and self.tools.linear:
            await self._cache_team_metadata()

    async def handle_event(self, event: Event) -> None:
        match event.kind:
            case "idea_submitted":
                await self._process_idea(event.payload)
            case "feedback_received":
                await self._triage_feedback(event.payload)
            case _:
                logger.debug("%s ignoring event kind=%s", self.name, event.kind)

    # ── internal logic ──────────────────────────────────────────────

    async def _cache_team_metadata(self) -> None:
        assert self.tools.linear
        self._team_id = await self.tools.linear.get_team_id(self._team_key)
        states = await self.tools.linear.get_workflow_states(self._team_id)
        self._workflow_states = {s["name"]: s["id"] for s in states}
        logger.info("Cached team %s (%s) with %d states", self._team_key, self._team_id, len(self._workflow_states))

    async def _process_idea(self, payload: dict[str, Any]) -> None:
        assert self.tools.linear and self._team_id
        title = payload["title"]
        description = payload.get("description", "")

        # Create the epic
        epic = await self.tools.linear.create_issue(
            team_id=self._team_id,
            title=f"[Epic] {title}",
            description=f"## Overview\n\n{description}",
            priority=self._default_priority,
        )
        logger.info("Created epic %s: %s", epic["identifier"], epic["url"])

        # Break down into sub-tickets if breakdown is provided
        for task in payload.get("breakdown", []):
            sub = await self.tools.linear.create_issue(
                team_id=self._team_id,
                title=task["title"],
                description=task.get("description", ""),
                priority=task.get("priority", self._default_priority),
                parent_id=epic["id"],
            )
            logger.info("  Created sub-ticket %s", sub["identifier"])

        # Notify Slack
        if self.tools.slack and (channel := payload.get("slack_channel")):
            await self.tools.slack.post_message(
                channel,
                f"New epic created: *{epic['identifier']}* \u2014 {title}\n{epic['url']}",
            )

    async def _triage_feedback(self, payload: dict[str, Any]) -> None:
        assert self.tools.linear and self._team_id
        issue = await self.tools.linear.create_issue(
            team_id=self._team_id,
            title=f"[Feedback] {payload.get('summary', 'User feedback')}",
            description=payload.get("body", ""),
            priority=payload.get("priority", 4),
        )
        logger.info("Triaged feedback as %s", issue["identifier"])
