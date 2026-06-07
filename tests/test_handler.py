"""Tests for opencode_github.handler."""

from __future__ import annotations

import hashlib
import hmac
import json

import httpx
import respx

from opencode_github.config import Config
from opencode_github.handler import WebhookProcessor

BASE = "https://api.github.com"


def _sign(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _make_config() -> Config:
    return Config(
        github_token="test-token",
        anthropic_api_key="test-key",
        github_api_url=BASE,
    )


def _issue_comment_body(comment_text: str = "/oc fix the bug") -> bytes:
    return json.dumps(
        {
            "action": "created",
            "issue": {"number": 42},
            "comment": {
                "id": 1001,
                "body": comment_text,
                "user": {"login": "contributor"},
                "html_url": "https://github.com/owner/repo/issues/42#issuecomment-1001",
            },
            "repository": {
                "name": "repo",
                "owner": {"login": "owner"},
            },
        }
    ).encode()


class TestProcess:
    async def test_valid_command_acknowledged(self) -> None:
        config = _make_config()
        body = _issue_comment_body()

        with respx.mock(base_url=BASE, assert_all_called=False) as router:
            router.post("/repos/owner/repo/issues/comments/1001/reactions").mock(
                return_value=httpx.Response(201, json={"id": 1, "content": "eyes"})
            )
            async with WebhookProcessor(config) as processor:
                result = await processor.process("issue_comment", body)

        assert result.event is not None
        assert result.acknowledged is True
        assert len(result.commands) == 1
        assert result.commands[0].trigger == "/oc"
        assert result.commands[0].arguments == "fix the bug"
        assert result.skipped_reason == ""

    async def test_no_commands_skipped(self) -> None:
        config = _make_config()
        body = _issue_comment_body("just a regular comment")

        async with WebhookProcessor(config) as processor:
            result = await processor.process("issue_comment", body)

        assert result.event is not None
        assert result.acknowledged is False
        assert result.commands == []
        assert result.skipped_reason == "no_commands"

    async def test_unsupported_event_skipped(self) -> None:
        config = _make_config()
        body = json.dumps({"action": "created"}).encode()

        async with WebhookProcessor(config) as processor:
            result = await processor.process("push", body)

        assert result.event is None
        assert result.skipped_reason == "unsupported_event"

    async def test_signature_verification_pass(self) -> None:
        secret = "webhook-secret"
        config = _make_config()
        body = _issue_comment_body()
        sig = _sign(body, secret)

        with respx.mock(base_url=BASE, assert_all_called=False) as router:
            router.post("/repos/owner/repo/issues/comments/1001/reactions").mock(
                return_value=httpx.Response(201, json={"id": 1, "content": "eyes"})
            )
            async with WebhookProcessor(config, webhook_secret=secret) as processor:
                result = await processor.process("issue_comment", body, signature=sig)

        assert result.acknowledged is True

    async def test_signature_verification_fail(self) -> None:
        secret = "webhook-secret"
        config = _make_config()
        body = _issue_comment_body()

        async with WebhookProcessor(config, webhook_secret=secret) as processor:
            result = await processor.process("issue_comment", body, signature="sha256=bad")

        assert result.event is None
        assert result.skipped_reason == "invalid_signature"

    async def test_missing_signature_when_secret_set(self) -> None:
        config = _make_config()

        async with WebhookProcessor(config, webhook_secret="secret") as processor:
            result = await processor.process("issue_comment", b"{}", signature=None)

        assert result.skipped_reason == "invalid_signature"

    async def test_acknowledge_failure_does_not_raise(self) -> None:
        config = _make_config()
        body = _issue_comment_body()

        with respx.mock(base_url=BASE, assert_all_called=False) as router:
            router.post("/repos/owner/repo/issues/comments/1001/reactions").mock(
                return_value=httpx.Response(500, text="Internal Server Error")
            )
            async with WebhookProcessor(config) as processor:
                result = await processor.process("issue_comment", body)

        assert result.commands != []
        assert result.acknowledged is True

    async def test_multiple_commands_extracted(self) -> None:
        config = _make_config()
        body = _issue_comment_body("/oc first task\nsome text\n/opencode second task")

        with respx.mock(base_url=BASE, assert_all_called=False) as router:
            router.post("/repos/owner/repo/issues/comments/1001/reactions").mock(
                return_value=httpx.Response(201, json={"id": 1, "content": "eyes"})
            )
            async with WebhookProcessor(config) as processor:
                result = await processor.process("issue_comment", body)

        assert len(result.commands) == 2
        assert result.commands[0].arguments == "first task"
        assert result.commands[1].arguments == "second task"


class TestBotLoopPrevention:
    async def test_ignored_login_skipped(self) -> None:
        config = _make_config()
        body = _issue_comment_body("/oc do something")

        async with WebhookProcessor(config, ignore_logins={"contributor"}) as processor:
            result = await processor.process("issue_comment", body)

        assert result.event is not None
        assert result.skipped_reason == "ignored_login"
        assert result.commands == []
        assert result.acknowledged is False

    async def test_non_ignored_login_processed(self) -> None:
        config = _make_config()
        body = _issue_comment_body("/oc do something")

        with respx.mock(base_url=BASE, assert_all_called=False) as router:
            router.post("/repos/owner/repo/issues/comments/1001/reactions").mock(
                return_value=httpx.Response(201, json={"id": 1, "content": "eyes"})
            )
            async with WebhookProcessor(config, ignore_logins={"some-other-bot"}) as processor:
                result = await processor.process("issue_comment", body)

        assert result.acknowledged is True
        assert len(result.commands) == 1

    async def test_empty_ignore_set_processes_all(self) -> None:
        config = _make_config()
        body = _issue_comment_body("/oc hello")

        with respx.mock(base_url=BASE, assert_all_called=False) as router:
            router.post("/repos/owner/repo/issues/comments/1001/reactions").mock(
                return_value=httpx.Response(201, json={"id": 1, "content": "eyes"})
            )
            async with WebhookProcessor(config, ignore_logins=set()) as processor:
                result = await processor.process("issue_comment", body)

        assert result.acknowledged is True


class TestContextManager:
    async def test_async_with(self) -> None:
        config = _make_config()
        async with WebhookProcessor(config) as processor:
            assert processor._config is config
