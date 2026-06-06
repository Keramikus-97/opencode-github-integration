"""Shared HTTP helpers for GitHub API interactions.

Both ``github_client`` and ``webhook_handler`` (and any future HTTP-facing
module) use these helpers for header construction, response parsing, and
client creation rather than duplicating httpx boilerplate.
"""

from __future__ import annotations

from typing import Any

import httpx

from opencode_github.utils.errors import GitHubAPIError

_DEFAULT_ACCEPT = "application/vnd.github+json"
_API_VERSION = "2022-11-28"


def build_headers(
    token: str,
    *,
    accept: str = _DEFAULT_ACCEPT,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build standard GitHub API request headers."""
    headers: dict[str, str] = {
        "Accept": accept,
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": _API_VERSION,
    }
    if extra:
        headers.update(extra)
    return headers


def parse_json_response(response: httpx.Response) -> Any:
    """Parse a GitHub API JSON response, raising on error status codes."""
    if response.status_code >= 400:
        raise GitHubAPIError(
            f"GitHub API error: {response.status_code} {response.reason_phrase}",
            status_code=response.status_code,
            context={"url": str(response.url), "body": response.text[:500]},
        )
    if not response.content:
        return None
    return response.json()


def create_http_client(
    *,
    token: str | None = None,
    base_url: str = "https://api.github.com",
    timeout: float = 30.0,
) -> httpx.AsyncClient:
    """Create a pre-configured async HTTP client for GitHub API calls."""
    headers = build_headers(token) if token else {}
    return httpx.AsyncClient(
        base_url=base_url,
        headers=headers,
        timeout=timeout,
    )
