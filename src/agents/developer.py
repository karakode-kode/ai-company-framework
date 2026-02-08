from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.agents.base_agent import BaseAgent, Event, ToolBox

logger = logging.getLogger(__name__)


class DeveloperAgent(BaseAgent):
    """Picks up assigned Linear tickets, writes code via Claude Code CLI, and opens PRs."""

    def __init__(self, tools: ToolBox, config: dict[str, Any]) -> None:
        super().__init__(name="Developer", tools=tools, config=config)
        self._github_org: str = config.get("github_org", "")
        self._branch_prefix: str = config.get("branch_prefix", "ai/")
        self._auto_pr: bool = config.get("auto_pr", True)
        self._max_concurrent: int = config.get("max_concurrent_tickets", 2)
        self._active_tickets: set[str] = set()
        self._assignee_id: str | None = None

    async def poll(self) -> None:
        """Check Linear for tickets in 'Todo' assigned to this agent."""
        if not self.tools.linear or not self._assignee_id:
            return
        if len(self._active_tickets) >= self._max_concurrent:
            return

        tickets = await self.tools.linear.get_assigned_issues(self._assignee_id, state_name="Todo")
        for ticket in tickets:
            if ticket["id"] not in self._active_tickets:
                self.push_event(Event(kind="ticket_assigned", source="poll", payload=ticket))

    async def handle_event(self, event: Event) -> None:
        match event.kind:
            case "ticket_assigned":
                await self._work_on_ticket(event.payload)
            case "pr_review_requested":
                await self._handle_review_feedback(event.payload)
            case _:
                logger.debug("%s ignoring event kind=%s", self.name, event.kind)

    # ── internal logic ──────────────────────────────────────────────

    async def _work_on_ticket(self, ticket: dict[str, Any]) -> None:
        ticket_id = ticket["id"]
        identifier = ticket["identifier"]

        if ticket_id in self._active_tickets:
            return
        self._active_tickets.add(ticket_id)

        logger.info("Starting work on %s: %s", identifier, ticket["title"])
        try:
            branch_name = f"{self._branch_prefix}{identifier.lower()}"
            repo = self._infer_repo(ticket)

            # Invoke Claude Code CLI to implement the ticket
            await self._run_claude_code(
                repo=repo,
                branch=branch_name,
                ticket=ticket,
            )

            # Open PR if configured
            if self._auto_pr and self.tools.github:
                pr = await self.tools.github.create_pull_request(
                    owner=self._github_org,
                    repo=repo,
                    title=f"{identifier}: {ticket['title']}",
                    head=branch_name,
                    base="main",
                    body=self._format_pr_body(ticket),
                )
                logger.info("Opened PR #%d for %s", pr["number"], identifier)

                if self.tools.slack:
                    await self.tools.slack.post_message(
                        "engineering",
                        f"PR opened for *{identifier}*: {pr['html_url']}",
                    )
        except Exception:
            logger.exception("Failed to complete %s", identifier)
        finally:
            self._active_tickets.discard(ticket_id)

    async def _run_claude_code(self, repo: str, branch: str, ticket: dict[str, Any]) -> None:
        prompt = (
            f"Implement the following ticket.\n\n"
            f"Title: {ticket['title']}\n"
            f"Description: {ticket.get('description', 'No description')}\n\n"
            f"Work on branch '{branch}' in repo '{self._github_org}/{repo}'. "
            f"Commit your changes with a message referencing {ticket['identifier']}."
        )
        proc = await asyncio.create_subprocess_exec(
            "claude", "--yes", "--print", prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(
                f"Claude Code exited with {proc.returncode}: {stderr.decode()[:500]}"
            )
        logger.info("Claude Code output for %s:\n%s", ticket["identifier"], stdout.decode()[:1000])

    async def _handle_review_feedback(self, payload: dict[str, Any]) -> None:
        logger.info("Review feedback received for PR #%s \u2014 re-running implementation", payload.get("pr_number"))

    def _infer_repo(self, ticket: dict[str, Any]) -> str:
        for label in ticket.get("labels", {}).get("nodes", []):
            if label["name"].startswith("repo:"):
                return label["name"].removeprefix("repo:")
        return "ai-company-framework"

    @staticmethod
    def _format_pr_body(ticket: dict[str, Any]) -> str:
        return (
            f"## {ticket['identifier']}: {ticket['title']}\n\n"
            f"{ticket.get('description', '')}\n\n"
            f"---\n"
            f"*Automatically generated by AI Developer Agent*"
        )
