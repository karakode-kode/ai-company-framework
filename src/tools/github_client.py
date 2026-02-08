from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

API_BASE = "https://api.github.com"


class GitHubClient:
    """Async wrapper around the GitHub REST API."""

    def __init__(self, token: str) -> None:
        self._http = httpx.AsyncClient(
            base_url=API_BASE,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )

    async def create_branch(self, owner: str, repo: str, branch: str, from_sha: str) -> dict[str, Any]:
        resp = await self._http.post(
            f"/repos/{owner}/{repo}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": from_sha},
        )
        resp.raise_for_status()
        return resp.json()

    async def get_default_branch_sha(self, owner: str, repo: str) -> str:
        resp = await self._http.get(f"/repos/{owner}/{repo}")
        resp.raise_for_status()
        default_branch = resp.json()["default_branch"]
        ref_resp = await self._http.get(f"/repos/{owner}/{repo}/git/ref/heads/{default_branch}")
        ref_resp.raise_for_status()
        return ref_resp.json()["object"]["sha"]

    async def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        head: str,
        base: str,
        body: str = "",
    ) -> dict[str, Any]:
        resp = await self._http.post(
            f"/repos/{owner}/{repo}/pulls",
            json={"title": title, "head": head, "base": base, "body": body},
        )
        resp.raise_for_status()
        return resp.json()

    async def get_pr_status(self, owner: str, repo: str, pr_number: int) -> dict[str, Any]:
        resp = await self._http.get(f"/repos/{owner}/{repo}/pulls/{pr_number}")
        resp.raise_for_status()
        return resp.json()

    async def list_open_prs(self, owner: str, repo: str) -> list[dict[str, Any]]:
        resp = await self._http.get(
            f"/repos/{owner}/{repo}/pulls",
            params={"state": "open", "per_page": 30},
        )
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        await self._http.aclose()
