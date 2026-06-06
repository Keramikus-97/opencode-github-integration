"""Tests for the webhook handler module."""

from __future__ import annotations

import pytest

from opencode_github.utils.crypto import compute_hmac_sha256
from opencode_github.utils.errors import WebhookValidationError
from opencode_github.webhook_handler import (
    EventType,
    parse_event,
    verify_signature,
)


class TestEventType:
    def test_issue_comment(self) -> None:
        assert EventType.from_header("issue_comment") is EventType.ISSUE_COMMENT

    def test_pr_review_comment(self) -> None:
        assert (
            EventType.from_header("pull_request_review_comment")
            is EventType.PR_REVIEW_COMMENT
        )

    def test_unknown(self) -> None:
        assert EventType.from_header("push") is EventType.UNKNOWN

    def test_case_insensitive(self) -> None:
        assert EventType.from_header("Issue_Comment") is EventType.ISSUE_COMMENT


class TestVerifySignature:
    def test_valid_signature(self) -> None:
        payload = '{"action": "created"}'
        secret = "test-secret"
        sig = compute_hmac_sha256(secret, payload)
        verify_signature(payload, secret, f"sha256={sig}")

    def test_invalid_signature_raises(self) -> None:
        with pytest.raises(WebhookValidationError, match="signature verification"):
            verify_signature("payload", "secret", "sha256=badbeef")


class TestParseEvent:
    def test_issue_comment_event(self) -> None:
        payload = {
            "action": "created",
            "comment": {
                "body": "/oc fix bug",
                "user": {"login": "alice"},
            },
            "issue": {"number": 42},
            "repository": {"full_name": "org/repo"},
        }

        event = parse_event("issue_comment", payload)

        assert event.event_type is EventType.ISSUE_COMMENT
        assert event.action == "created"
        assert event.comment_body == "/oc fix bug"
        assert event.repo_full_name == "org/repo"
        assert event.issue_number == 42
        assert event.sender == "alice"

    def test_pr_review_comment_event(self) -> None:
        payload = {
            "action": "created",
            "comment": {
                "body": "/opencode review this",
                "user": {"login": "bob"},
            },
            "pull_request": {"number": 7},
            "repository": {"full_name": "org/repo"},
        }

        event = parse_event("pull_request_review_comment", payload)

        assert event.event_type is EventType.PR_REVIEW_COMMENT
        assert event.issue_number == 7

    def test_missing_fields_default_gracefully(self) -> None:
        event = parse_event("unknown_event", {})

        assert event.event_type is EventType.UNKNOWN
        assert event.action == ""
        assert event.comment_body == ""
        assert event.issue_number == 0
