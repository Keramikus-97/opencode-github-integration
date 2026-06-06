"""Tests for the GitHub client module."""

from __future__ import annotations

import pytest

from opencode_github.github_client import GitHubClient
from opencode_github.utils.errors import GitHubAPIError


class TestGitHubClientLifecycle:
    @pytest.mark.asyncio
    async def test_raises_without_context_manager(self) -> None:
        client = GitHubClient(token="test-token")
        with pytest.raises(GitHubAPIError, match="not initialised"):
            await client.get_issue("owner", "repo", 1)

    @pytest.mark.asyncio
    async def test_context_manager_initialises_client(self) -> None:
        async with GitHubClient(token="test-token") as client:
            assert client._client is not None

    @pytest.mark.asyncio
    async def test_context_manager_closes_client(self) -> None:
        client = GitHubClient(token="test-token")
        async with client:
            pass
        assert client._client is None
