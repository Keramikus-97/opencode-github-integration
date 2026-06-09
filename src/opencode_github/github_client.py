"""Thin async wrapper around the GitHub REST API."""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx

from opencode_github.config import Config

# Server-side status codes worth retrying as transient failures.
RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({500, 502, 503, 504})


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
    """Raised when the GitHub rate limit is exhausted after all retries.

    Parameters
    ----------
    status_code:
        The HTTP status code returned (``429`` or ``403``).
    detail:
        Response body text.
    retry_after:
        Parsed ``Retry-After`` header value in seconds, when present.
    reset_at:
        Parsed ``X-RateLimit-Reset`` header value (epoch seconds), when present.
    """

    def __init__(
        self,
        status_code: int,
        detail: str,
        retry_after: float | None = None,
        reset_at: float | None = None,
    ) -> None:
        self.retry_after = retry_after
        self.reset_at = reset_at
        super().__init__(status_code, detail)


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
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        max_backoff: float = 60.0,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._max_retries = max(0, max_retries)
        self._backoff_factor = backoff_factor
        self._max_backoff = max_backoff
        self._sleep = sleep or asyncio.sleep
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=timeout,
        )

    @classmethod
    def from_config(
        cls,
        config: Config,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> GitHubClient:
        """Build a client from a :class:`~opencode_github.config.Config`."""
        return cls(
            token=config.github_token,
            base_url=config.github_api_url,
            timeout=config.request_timeout,
            max_retries=config.max_retries,
            backoff_factor=config.backoff_factor,
            sleep=sleep,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> GitHubClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    @staticmethod
    def _is_rate_limited(resp: httpx.Response) -> bool:
        """Return ``True`` when a response indicates a rate-limit condition.

        GitHub signals primary rate limits with ``403`` and
        ``X-RateLimit-Remaining: 0`` and secondary rate limits with ``429`` or
        a ``Retry-After`` header.
        """
        if resp.status_code == 429:
            return True
        if resp.status_code == 403:
            if resp.headers.get("x-ratelimit-remaining") == "0":
                return True
            if resp.headers.get("retry-after"):
                return True
        return False

    def _backoff_delay(self, attempt: int) -> float:
        """Exponential backoff with full jitter for retry *attempt* (0-based)."""
        base = self._backoff_factor * (2**attempt)
        jitter = random.uniform(0, self._backoff_factor)
        return min(base + jitter, self._max_backoff)

    def _retry_delay(self, resp: httpx.Response, attempt: int) -> float:
        """Compute the delay before retrying a rate-limited *resp*.

        Honors ``Retry-After`` and ``X-RateLimit-Reset`` headers, falling back
        to exponential backoff.
        """
        retry_after = resp.headers.get("retry-after")
        if retry_after:
            try:
                return min(max(0.0, float(retry_after)), self._max_backoff)
            except ValueError:
                pass

        if resp.headers.get("x-ratelimit-remaining") == "0":
            reset = resp.headers.get("x-ratelimit-reset")
            if reset:
                try:
                    delay = float(reset) - time.time()
                except ValueError:
                    delay = 0.0
                if delay > 0:
                    return min(delay, self._max_backoff)

        return self._backoff_delay(attempt)

    @staticmethod
    def _rate_limit_error(resp: httpx.Response) -> RateLimitError:
        retry_after: float | None = None
        raw_retry_after = resp.headers.get("retry-after")
        if raw_retry_after:
            try:
                retry_after = float(raw_retry_after)
            except ValueError:
                retry_after = None

        reset_at: float | None = None
        raw_reset = resp.headers.get("x-ratelimit-reset")
        if raw_reset:
            try:
                reset_at = float(raw_reset)
            except ValueError:
                reset_at = None

        return RateLimitError(resp.status_code, resp.text, retry_after, reset_at)

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        attempt = 0
        while True:
            try:
                resp = await self._client.request(method, path, **kwargs)
            except httpx.TransportError:
                if attempt >= self._max_retries:
                    raise
                await self._sleep(self._backoff_delay(attempt))
                attempt += 1
                continue

            if self._is_rate_limited(resp):
                if attempt < self._max_retries:
                    await self._sleep(self._retry_delay(resp, attempt))
                    attempt += 1
                    continue
                raise self._rate_limit_error(resp)

            if resp.status_code in RETRYABLE_STATUS_CODES:
                if attempt < self._max_retries:
                    await self._sleep(self._backoff_delay(attempt))
                    attempt += 1
                    continue
                raise GitHubAPIError(resp.status_code, resp.text)

            if resp.status_code >= 400:
                raise GitHubAPIError(resp.status_code, resp.text)
            if resp.status_code == 204:
                return None
            return resp.json()

    async def get_pull_request(self, owner: str, repo: str, number: int) -> PullRequest:
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
