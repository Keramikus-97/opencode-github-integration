"""Asynchronous GitHub REST API client.

Delegates HTTP mechanics to ``utils.http`` and uses ``utils.errors`` for
error handling — no duplicated httpx setup or header construction here.
"""

from __future__ import annotations

from typing import Any

import httpx

from opencode_github.utils.errors import GitHubAPIError
from opencode_github.utils.http import create_http_client, parse_json_response


class GitHubClient:
    """Thin async wrapper around the GitHub REST API."""

    def __init__(
        self, token: str, *, base_url: str = "https://api.github.com"
    ) -> None:
        self._client: httpx.AsyncClient | None = None
        self._token = token
        self._base_url = base_url

    async def __aenter__(self) -> GitHubClient:
        self._client = create_http_client(
            token=self._token, base_url=self._base_url
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise GitHubAPIError(
                "Client not initialised; use 'async with' context manager"
            )
        return self._client

    async def get_issue(
        self, owner: str, repo: str, number: int
    ) -> dict[str, Any]:
        """Fetch an issue by owner/repo/number."""
        client = self._ensure_client()
        resp = await client.get(f"/repos/{owner}/{repo}/issues/{number}")
        return parse_json_response(resp)

    async def create_comment(
        self, owner: str, repo: str, number: int, body: str
    ) -> dict[str, Any]:
        """Post a comment on an issue or pull request."""
        client = self._ensure_client()
        resp = await client.post(
            f"/repos/{owner}/{repo}/issues/{number}/comments",
            json={"body": body},
        )
        return parse_json_response(resp)

    async def get_pull_request(
        self, owner: str, repo: str, number: int
    ) -> dict[str, Any]:
        """Fetch a pull request by owner/repo/number."""
        client = self._ensure_client()
        resp = await client.get(f"/repos/{owner}/{repo}/pulls/{number}")
        return parse_json_response(resp)
