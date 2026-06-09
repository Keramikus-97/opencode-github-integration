"""Thin async wrapper around the GitHub REST API."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import httpx

_SAFE_PATH_SEGMENT = re.compile(r"^[a-zA-Z0-9._-]+$")


def _validate_path_segment(value: str, name: str) -> str:
    """Ensure a URL path segment contains no path-traversal characters."""
    if not value or not _SAFE_PATH_SEGMENT.match(value):
        raise ValueError(f"Invalid {name}: {value!r}")
    return value


@dataclass(frozen=True)
class PullRequest:
    """Minimal pull-request representation."""

    number: int
    title: str
    head_ref: str
    base_ref: str
    body: str


@dataclass(frozen=True)
class IssueComment:
    """Minimal issue/PR comment representation."""

    id: int
    body: str
    user_login: str
    html_url: str


class GitHubAPIError(Exception):
    """Raised when an API request returns a non-success status."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"GitHub API error {status_code}: {detail}")


class GitHubClient:
    """Async GitHub REST API client.

    Parameters
    ----------
    token:
        Personal-access or installation token.
    base_url:
        API root, e.g. ``https://api.github.com``.
    timeout:
        HTTP timeout in seconds.
    """

    def __init__(
        self,
        token: str,
        base_url: str = "https://api.github.com",
        timeout: int = 30,
    ) -> None:
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=timeout,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> GitHubClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        resp = await self._client.request(method, path, **kwargs)
        if resp.status_code >= 400:
            raise GitHubAPIError(resp.status_code, resp.text)
        if resp.status_code == 204:
            return None
        return resp.json()

    async def get_pull_request(self, owner: str, repo: str, number: int) -> PullRequest:
        _validate_path_segment(owner, "owner")
        _validate_path_segment(repo, "repo")
        data = await self._request("GET", f"/repos/{owner}/{repo}/pulls/{number}")
        return PullRequest(
            number=data["number"],
            title=data["title"],
            head_ref=data["head"]["ref"],
            base_ref=data["base"]["ref"],
            body=data.get("body") or "",
        )

    async def list_issue_comments(
        self, owner: str, repo: str, issue_number: int
    ) -> list[IssueComment]:
        _validate_path_segment(owner, "owner")
        _validate_path_segment(repo, "repo")
        data = await self._request("GET", f"/repos/{owner}/{repo}/issues/{issue_number}/comments")
        return [
            IssueComment(
                id=c["id"],
                body=c.get("body") or "",
                user_login=c["user"]["login"],
                html_url=c["html_url"],
            )
            for c in data
        ]

    async def create_issue_comment(
        self, owner: str, repo: str, issue_number: int, body: str
    ) -> IssueComment:
        _validate_path_segment(owner, "owner")
        _validate_path_segment(repo, "repo")
        data = await self._request(
            "POST",
            f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
            json={"body": body},
        )
        return IssueComment(
            id=data["id"],
            body=data.get("body") or "",
            user_login=data["user"]["login"],
            html_url=data["html_url"],
        )

    async def add_reaction(
        self, owner: str, repo: str, comment_id: int, reaction: str = "+1"
    ) -> None:
        _validate_path_segment(owner, "owner")
        _validate_path_segment(repo, "repo")
        await self._request(
            "POST",
            f"/repos/{owner}/{repo}/issues/comments/{comment_id}/reactions",
            json={"content": reaction},
        )

    async def get_repo(self, owner: str, repo: str) -> dict[str, Any]:
        _validate_path_segment(owner, "owner")
        _validate_path_segment(repo, "repo")
        return await self._request("GET", f"/repos/{owner}/{repo}")
