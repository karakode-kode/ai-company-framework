from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Any

from src.tools.github_client import GitHubClient
from src.tools.linear_client import LinearClient
from src.tools.slack_client import SlackClient

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    IDLE = auto()
    RUNNING = auto()
    STOPPING = auto()
    ERRORED = auto()


class Event:
    """A typed event flowing through the agent system."""

    __slots__ = ("kind", "source", "payload")

    def __init__(self, kind: str, source: str, payload: dict[str, Any]) -> None:
        self.kind = kind
        self.source = source
        self.payload = payload

    def __repr__(self) -> str:
        return f"Event(kind={self.kind!r}, source={self.source!r})"


class ToolBox:
    """Container that holds initialized tool clients available to an agent."""

    def __init__(
        self,
        linear: LinearClient | None = None,
        github: GitHubClient | None = None,
        slack: SlackClient | None = None,
    ) -> None:
        self.linear = linear
        self.github = github
        self.slack = slack

    async def close(self) -> None:
        for client in (self.linear, self.github, self.slack):
            if client:
                await client.close()


class BaseAgent(ABC):
    """Abstract base class for all autonomous agents.

    Subclasses must implement:
        - handle_event: React to an incoming event.
        - poll: Perform periodic work (check for new tasks, etc.).
    """

    def __init__(self, name: str, tools: ToolBox, config: dict[str, Any]) -> None:
        self.name = name
        self.tools = tools
        self.config = config
        self.status = AgentStatus.IDLE
        self._event_queue: asyncio.Queue[Event] = asyncio.Queue()
        self._poll_interval: float = config.get("poll_interval_seconds", 30)
        self._max_retries: int = config.get("max_retries", 3)
        self._retry_backoff: float = config.get("retry_backoff_seconds", 5)

    # ── public interface ────────────────────────────────────────────

    async def start(self) -> None:
        """Run the agent's poll + event loops concurrently."""
        self.status = AgentStatus.RUNNING
        logger.info("%s agent started", self.name)
        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(self._poll_loop())
                tg.create_task(self._event_loop())
        except* Exception as exc_group:
            self.status = AgentStatus.ERRORED
            for exc in exc_group.exceptions:
                logger.error("%s agent crashed: %s", self.name, exc)
            raise

    async def stop(self) -> None:
        self.status = AgentStatus.STOPPING
        logger.info("%s agent stopping", self.name)

    def push_event(self, event: Event) -> None:
        self._event_queue.put_nowait(event)

    # ── abstract methods ────────────────────────────────────────────

    @abstractmethod
    async def handle_event(self, event: Event) -> None:
        """Process a single event. Must be implemented by subclasses."""

    @abstractmethod
    async def poll(self) -> None:
        """Periodic polling logic. Must be implemented by subclasses."""

    # ── internal loops ──────────────────────────────────────────────

    async def _poll_loop(self) -> None:
        while self.status == AgentStatus.RUNNING:
            try:
                await self.poll()
            except Exception:
                logger.exception("%s poll error", self.name)
            await asyncio.sleep(self._poll_interval)

    async def _event_loop(self) -> None:
        while self.status == AgentStatus.RUNNING:
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
            except TimeoutError:
                continue
            await self._dispatch_event(event)

    async def _dispatch_event(self, event: Event) -> None:
        for attempt in range(1, self._max_retries + 1):
            try:
                await self.handle_event(event)
                return
            except Exception:
                logger.exception(
                    "%s failed handling %s (attempt %d/%d)",
                    self.name,
                    event,
                    attempt,
                    self._max_retries,
                )
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_backoff * attempt)
        logger.error("%s gave up on %s after %d retries", self.name, event, self._max_retries)
