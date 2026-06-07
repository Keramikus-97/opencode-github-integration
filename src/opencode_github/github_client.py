"""Thin async wrapper around the GitHub REST API with retry and rate-limit support."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_BACKOFF_BASE = 1.0


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


class RateLimitError(GitHubAPIError):
    """Raised when the API rate limit is exhausted and retries are exceeded."""

    def __init__(self, reset_at: float, detail: str) -> None:
        self.reset_at = reset_at
        super().__init__(status_code=429, detail=detail)


class GitHubClient:
    """Async GitHub REST API client with automatic retries and rate-limit handling.

    Parameters
    ----------
    token:
        Personal-access or installation token.
    base_url:
        API root, e.g. ``https://api.github.com``.
    timeout:
        HTTP timeout in seconds.
    max_retries:
        Number of retries for transient failures (429, 5xx).
    backoff_base:
        Base delay in seconds for exponential backoff between retries.
    """

    def __init__(
        self,
        token: str,
        base_url: str = "https://api.github.com",
        timeout: int = 30,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        backoff_base: float = _DEFAULT_BACKOFF_BASE,
    ) -> None:
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._max_retries = max_retries
        self._backoff_base = backoff_base
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

    def _get_retry_delay(self, response: httpx.Response, attempt: int) -> float:
        """Determine how long to wait before retrying.

        Uses ``Retry-After`` or ``X-RateLimit-Reset`` headers when available,
        otherwise falls back to exponential backoff.
        """
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass

        reset_header = response.headers.get("X-RateLimit-Reset")
        if reset_header:
            try:
                reset_time = float(reset_header)
                wait = reset_time - time.time()
                if wait > 0:
                    return min(wait, 60.0)
            except ValueError:
                pass

        return self._backoff_base * (2**attempt)

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        last_exc: GitHubAPIError | None = None

        for attempt in range(self._max_retries + 1):
            resp = await self._client.request(method, path, **kwargs)

            if resp.status_code < 400:
                if resp.status_code == 204:
                    return None
                return resp.json()

            if resp.status_code not in _RETRYABLE_STATUS_CODES or attempt == self._max_retries:
                if resp.status_code == 429:
                    reset_at = float(resp.headers.get("X-RateLimit-Reset", 0))
                    raise RateLimitError(reset_at=reset_at, detail=resp.text)
                raise GitHubAPIError(resp.status_code, resp.text)

            delay = self._get_retry_delay(resp, attempt)
            logger.debug(
                "Retrying %s %s (attempt %d/%d, status %d, delay %.1fs)",
                method,
                path,
                attempt + 1,
                self._max_retries,
                resp.status_code,
                delay,
            )
            last_exc = GitHubAPIError(resp.status_code, resp.text)
            await asyncio.sleep(delay)

        raise last_exc  # type: ignore[misc]

    async def get_pull_request(self, owner: str, repo: str, number: int) -> PullRequest:
        data = await self._request("GET", f"/repos/{owner}/{repo}/pulls/{number}")
        return PullRequest(
            number=data["number"],
            title=data["title"],
            head_ref=data["head"]["ref"],
            base_ref=data["base"]["ref"],
            body=data.get("body") or "",
        )

    async def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        head: str,
        base: str,
        body: str = "",
        draft: bool = False,
    ) -> PullRequest:
        """Create a new pull request."""
        data = await self._request(
            "POST",
            f"/repos/{owner}/{repo}/pulls",
            json={
                "title": title,
                "head": head,
                "base": base,
                "body": body,
                "draft": draft,
            },
        )
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
        await self._request(
            "POST",
            f"/repos/{owner}/{repo}/issues/comments/{comment_id}/reactions",
            json={"content": reaction},
        )

    async def get_repo(self, owner: str, repo: str) -> dict[str, Any]:
        return await self._request("GET", f"/repos/{owner}/{repo}")

    async def update_file(
        self,
        owner: str,
        repo: str,
        path: str,
        message: str,
        content_b64: str,
        sha: str | None = None,
        branch: str | None = None,
    ) -> dict[str, Any]:
        """Create or update a file in the repository via the Contents API.

        Parameters
        ----------
        path:
            File path within the repository.
        message:
            Commit message.
        content_b64:
            Base64-encoded file content.
        sha:
            Blob SHA of the file being replaced (required for updates).
        branch:
            Target branch. Defaults to the repo's default branch.
        """
        payload: dict[str, Any] = {
            "message": message,
            "content": content_b64,
        }
        if sha:
            payload["sha"] = sha
        if branch:
            payload["branch"] = branch

        return await self._request(
            "PUT",
            f"/repos/{owner}/{repo}/contents/{path}",
            json=payload,
        )

    async def create_commit_status(
        self,
        owner: str,
        repo: str,
        sha: str,
        state: str,
        description: str = "",
        context: str = "opencode",
        target_url: str = "",
    ) -> dict[str, Any]:
        """Set a commit status (pending, success, failure, error)."""
        payload: dict[str, Any] = {"state": state, "context": context}
        if description:
            payload["description"] = description
        if target_url:
            payload["target_url"] = target_url

        return await self._request(
            "POST",
            f"/repos/{owner}/{repo}/statuses/{sha}",
            json=payload,
        )
