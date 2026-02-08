"""Main orchestrator — manages agent lifecycle, event routing, and the webhook server."""

from __future__ import annotations

import asyncio
import importlib
import logging
import os
import signal
from pathlib import Path
from typing import Any

import uvicorn
import yaml
from dotenv import load_dotenv

from src.agents.base_agent import BaseAgent, Event, ToolBox
from src.tools.github_client import GitHubClient
from src.tools.linear_client import LinearClient
from src.tools.slack_client import SlackClient
from src.webhook_server import create_app

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent


class Orchestrator:
    """Boots agents from config, runs them as concurrent async tasks, and routes events."""

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}
        self._tools: ToolBox | None = None
        self._shutdown = asyncio.Event()

    # ── bootstrap ───────────────────────────────────────────────

    def _load_config(self) -> dict[str, Any]:
        config_path = ROOT / "config" / "agents.yaml"
        with open(config_path) as f:
            return yaml.safe_load(f)

    def _build_toolbox(self) -> ToolBox:
        tools = ToolBox()
        if key := os.getenv("LINEAR_API_KEY"):
            tools.linear = LinearClient(api_key=key)
        if token := os.getenv("GITHUB_TOKEN"):
            tools.github = GitHubClient(token=token)
        if token := os.getenv("SLACK_BOT_TOKEN"):
            tools.slack = SlackClient(bot_token=token)
        return tools

    def _instantiate_agents(self, config: dict[str, Any]) -> None:
        defaults = config.get("defaults", {})
        for name, agent_cfg in config.get("agents", {}).items():
            if not agent_cfg.get("enabled", True):
                logger.info("Skipping disabled agent: %s", name)
                continue
            merged = {**defaults, **agent_cfg.get("config", {}), **{"poll_interval_seconds": agent_cfg.get("poll_interval_seconds", 30)}}
            cls = self._import_class(agent_cfg["class"])
            agent = cls(tools=self._tools, config=merged)
            self._agents[name] = agent
            logger.info("Registered agent: %s (%s)", name, cls.__name__)

    @staticmethod
    def _import_class(dotted_path: str) -> type:
        module_path, class_name = dotted_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)

    # ── event routing ───────────────────────────────────────────

    async def _route_event(self, event: Event) -> None:
        logger.info("Routing event: %s", event)
        for agent in self._agents.values():
            agent.push_event(event)

    # ── lifecycle ───────────────────────────────────────────────

    async def run(self) -> None:
        config = self._load_config()
        self._tools = self._build_toolbox()
        self._instantiate_agents(config)

        webhook_secret = os.getenv("WEBHOOK_SECRET", "")
        app = create_app(webhook_secret=webhook_secret, on_event=self._route_event)

        server_config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=int(os.getenv("PORT", "8000")),
            log_level="info",
        )
        server = uvicorn.Server(server_config)

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._shutdown.set)

        logger.info("Starting orchestrator with %d agent(s)", len(self._agents))
        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(server.serve())
                for agent in self._agents.values():
                    tg.create_task(agent.start())
                tg.create_task(self._wait_for_shutdown())
        finally:
            for agent in self._agents.values():
                await agent.stop()
            if self._tools:
                await self._tools.close()
            logger.info("Orchestrator shut down")

    async def _wait_for_shutdown(self) -> None:
        await self._shutdown.wait()
        raise SystemExit(0)


async def main() -> None:
    orchestrator = Orchestrator()
    await orchestrator.run()


if __name__ == "__main__":
    asyncio.run(main())
