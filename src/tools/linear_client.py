from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GRAPHQL_ENDPOINT = "https://api.linear.app/graphql"


class LinearClient:
    """Async wrapper around the Linear GraphQL API."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._http = httpx.AsyncClient(
            base_url=GRAPHQL_ENDPOINT,
            headers={
                "Authorization": api_key,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def _query(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables
        resp = await self._http.post("", json=payload)
        resp.raise_for_status()
        body = resp.json()
        if errors := body.get("errors"):
            raise RuntimeError(f"Linear GraphQL errors: {errors}")
        return body["data"]

    async def create_issue(
        self,
        team_id: str,
        title: str,
        description: str = "",
        priority: int = 3,
        labels: list[str] | None = None,
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        mutation = """
        mutation CreateIssue($input: IssueCreateInput!) {
            issueCreate(input: $input) {
                success
                issue { id identifier title url state { name } }
            }
        }
        """
        input_data: dict[str, Any] = {
            "teamId": team_id,
            "title": title,
            "description": description,
            "priority": priority,
        }
        if labels:
            input_data["labelIds"] = labels
        if parent_id:
            input_data["parentId"] = parent_id
        data = await self._query(mutation, {"input": input_data})
        return data["issueCreate"]["issue"]

    async def update_issue_state(self, issue_id: str, state_id: str) -> dict[str, Any]:
        mutation = """
        mutation UpdateIssue($id: String!, $input: IssueUpdateInput!) {
            issueUpdate(id: $id, input: $input) {
                success
                issue { id identifier state { name } }
            }
        }
        """
        data = await self._query(mutation, {"id": issue_id, "input": {"stateId": state_id}})
        return data["issueUpdate"]["issue"]

    async def get_team_id(self, team_key: str) -> str:
        query = """
        query Teams {
            teams { nodes { id key name } }
        }
        """
        data = await self._query(query)
        for team in data["teams"]["nodes"]:
            if team["key"] == team_key:
                return team["id"]
        raise ValueError(f"Team with key '{team_key}' not found")

    async def get_assigned_issues(self, assignee_id: str, state_name: str = "Todo") -> list[dict[str, Any]]:
        query = """
        query AssignedIssues($assigneeId: ID!, $stateName: String!) {
            issues(filter: {
                assignee: { id: { eq: $assigneeId } }
                state: { name: { eq: $stateName } }
            }) {
                nodes { id identifier title description priority labels { nodes { name } } }
            }
        }
        """
        data = await self._query(query, {"assigneeId": assignee_id, "stateName": state_name})
        return data["issues"]["nodes"]

    async def get_workflow_states(self, team_id: str) -> list[dict[str, Any]]:
        query = """
        query WorkflowStates($teamId: ID!) {
            workflowStates(filter: { team: { id: { eq: $teamId } } }) {
                nodes { id name type position }
            }
        }
        """
        data = await self._query(query, {"teamId": team_id})
        return data["workflowStates"]["nodes"]

    async def close(self) -> None:
        await self._http.aclose()
