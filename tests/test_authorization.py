"""Tests for opencode_github.authorization."""

from __future__ import annotations

import httpx
import pytest
import respx

from opencode_github.authorization import (
    check_event_authorization,
    is_authorized,
    permission_rank,
)
from opencode_github.github_client import GitHubClient
from opencode_github.webhook_handler import EventType, WebhookEvent

BASE = "https://api.github.com"


def _make_event(sender: str = "alice") -> WebhookEvent:
    return WebhookEvent(
        event_type=EventType.ISSUE_COMMENT,
        action="created",
        comment_body="/oc help",
        comment_id=42,
        sender_login=sender,
        repo_owner="owner",
        repo_name="repo",
        issue_number=7,
        raw_payload={},
    )


@pytest.fixture()
def mock_router() -> respx.MockRouter:
    with respx.mock(base_url=BASE, assert_all_called=False) as router:
        yield router


@pytest.fixture()
def client() -> GitHubClient:
    return GitHubClient(token="test-token", base_url=BASE, timeout=5)


class TestPermissionRank:
    def test_known_levels(self) -> None:
        assert permission_rank("admin") == 4
        assert permission_rank("maintain") == 3
        assert permission_rank("write") == 2
        assert permission_rank("triage") == 1
        assert permission_rank("read") == 0
        assert permission_rank("none") == -1

    def test_case_insensitive(self) -> None:
        assert permission_rank("ADMIN") == 4
        assert permission_rank("Write") == 2

    def test_unknown_treated_as_none(self) -> None:
        assert permission_rank("unknown") == -1
        assert permission_rank("") == -1


class TestIsAuthorized:
    def test_admin_always_passes(self) -> None:
        assert is_authorized("admin", "write") is True
        assert is_authorized("admin", "admin") is True

    def test_write_meets_write(self) -> None:
        assert is_authorized("write", "write") is True

    def test_read_below_write(self) -> None:
        assert is_authorized("read", "write") is False

    def test_none_below_everything(self) -> None:
        assert is_authorized("none", "read") is False

    def test_triage_below_write(self) -> None:
        assert is_authorized("triage", "write") is False

    def test_maintain_above_write(self) -> None:
        assert is_authorized("maintain", "write") is True

    def test_custom_min_level_read(self) -> None:
        assert is_authorized("read", "read") is True
        assert is_authorized("none", "read") is False


class TestCheckEventAuthorization:
    async def test_authorized_user(
        self, mock_router: respx.MockRouter, client: GitHubClient
    ) -> None:
        mock_router.get("/repos/owner/repo/collaborators/alice/permission").mock(
            return_value=httpx.Response(200, json={"permission": "write"})
        )
        event = _make_event("alice")
        result = await check_event_authorization(client, event)
        assert result is True

    async def test_admin_authorized(
        self, mock_router: respx.MockRouter, client: GitHubClient
    ) -> None:
        mock_router.get("/repos/owner/repo/collaborators/bob/permission").mock(
            return_value=httpx.Response(200, json={"permission": "admin"})
        )
        event = _make_event("bob")
        result = await check_event_authorization(client, event)
        assert result is True

    async def test_read_denied_posts_comment(
        self, mock_router: respx.MockRouter, client: GitHubClient
    ) -> None:
        mock_router.get("/repos/owner/repo/collaborators/eve/permission").mock(
            return_value=httpx.Response(200, json={"permission": "read"})
        )
        comment_route = mock_router.post("/repos/owner/repo/issues/7/comments").mock(
            return_value=httpx.Response(
                201,
                json={
                    "id": 99,
                    "body": "denied",
                    "user": {"login": "bot"},
                    "html_url": "https://github.com/owner/repo/issues/7#issuecomment-99",
                },
            )
        )
        event = _make_event("eve")
        result = await check_event_authorization(client, event)
        assert result is False
        assert comment_route.called

    async def test_denied_no_comment_when_disabled(
        self, mock_router: respx.MockRouter, client: GitHubClient
    ) -> None:
        mock_router.get("/repos/owner/repo/collaborators/eve/permission").mock(
            return_value=httpx.Response(200, json={"permission": "read"})
        )
        event = _make_event("eve")
        result = await check_event_authorization(client, event, post_denial=False)
        assert result is False

    async def test_api_error_defaults_to_denied(
        self, mock_router: respx.MockRouter, client: GitHubClient
    ) -> None:
        mock_router.get("/repos/owner/repo/collaborators/ghost/permission").mock(
            return_value=httpx.Response(403, json={"message": "Forbidden"})
        )
        mock_router.post("/repos/owner/repo/issues/7/comments").mock(
            return_value=httpx.Response(
                201,
                json={
                    "id": 100,
                    "body": "denied",
                    "user": {"login": "bot"},
                    "html_url": "https://github.com/owner/repo/issues/7#issuecomment-100",
                },
            )
        )
        event = _make_event("ghost")
        result = await check_event_authorization(client, event)
        assert result is False

    async def test_custom_min_level(
        self, mock_router: respx.MockRouter, client: GitHubClient
    ) -> None:
        mock_router.get("/repos/owner/repo/collaborators/alice/permission").mock(
            return_value=httpx.Response(200, json={"permission": "read"})
        )
        event = _make_event("alice")
        result = await check_event_authorization(client, event, min_level="read")
        assert result is True
