"""Tests for opencode_github.webhook_handler."""

from __future__ import annotations

import json

from opencode_github.webhook_handler import (
    EventType,
    classify_event,
    parse_payload,
    parse_raw,
    verify_signature,
)


class TestClassifyEvent:
    def test_issue_comment(self) -> None:
        assert classify_event("issue_comment") == EventType.ISSUE_COMMENT

    def test_pr_review_comment(self) -> None:
        assert classify_event("pull_request_review_comment") == EventType.PR_REVIEW_COMMENT

    def test_unknown(self) -> None:
        assert classify_event("push") == EventType.UNKNOWN

    def test_empty_string(self) -> None:
        assert classify_event("") == EventType.UNKNOWN


class TestVerifySignature:
    SECRET = "my-webhook-secret"

    def _sign(self, body: bytes) -> str:
        import hashlib
        import hmac

        digest = hmac.new(self.SECRET.encode(), body, hashlib.sha256).hexdigest()
        return f"sha256={digest}"

    def test_valid_signature(self) -> None:
        body = b'{"action":"created"}'
        sig = self._sign(body)
        assert verify_signature(body, sig, self.SECRET) is True

    def test_invalid_signature(self) -> None:
        body = b'{"action":"created"}'
        assert verify_signature(body, "sha256=deadbeef", self.SECRET) is False

    def test_empty_signature(self) -> None:
        assert verify_signature(b"data", "", self.SECRET) is False

    def test_empty_secret(self) -> None:
        assert verify_signature(b"data", "sha256=abc", "") is False

    def test_missing_sha256_prefix(self) -> None:
        body = b'{"action":"created"}'
        sig = self._sign(body).replace("sha256=", "md5=")
        assert verify_signature(body, sig, self.SECRET) is False

    def test_tampered_body(self) -> None:
        body = b'{"action":"created"}'
        sig = self._sign(body)
        assert verify_signature(b'{"action":"deleted"}', sig, self.SECRET) is False


class TestParsePayload:
    def test_issue_comment_created(self, issue_comment_payload: dict) -> None:
        event = parse_payload(EventType.ISSUE_COMMENT, issue_comment_payload)
        assert event is not None
        assert event.event_type == EventType.ISSUE_COMMENT
        assert event.action == "created"
        assert event.comment_body == "/oc fix the typo in README"
        assert event.comment_id == 1001
        assert event.sender_login == "contributor"
        assert event.repo_owner == "owner"
        assert event.repo_name == "repo"
        assert event.issue_number == 42

    def test_pr_review_comment_created(self, pr_review_comment_payload: dict) -> None:
        event = parse_payload(EventType.PR_REVIEW_COMMENT, pr_review_comment_payload)
        assert event is not None
        assert event.event_type == EventType.PR_REVIEW_COMMENT
        assert event.comment_body == "/opencode refactor this function"
        assert event.issue_number == 7

    def test_unknown_event_type(self, issue_comment_payload: dict) -> None:
        assert parse_payload(EventType.UNKNOWN, issue_comment_payload) is None

    def test_non_created_action(self, issue_comment_payload: dict) -> None:
        issue_comment_payload["action"] = "deleted"
        assert parse_payload(EventType.ISSUE_COMMENT, issue_comment_payload) is None

    def test_missing_comment(self) -> None:
        payload = {"action": "created", "repository": {"name": "r", "owner": {"login": "o"}}}
        assert parse_payload(EventType.ISSUE_COMMENT, payload) is None

    def test_missing_repo_info(self) -> None:
        payload = {
            "action": "created",
            "comment": {"id": 1, "body": "x", "user": {"login": "u"}, "html_url": ""},
            "issue": {"number": 1},
        }
        event = parse_payload(EventType.ISSUE_COMMENT, payload)
        assert event is not None
        assert event.repo_owner == ""
        assert event.repo_name == ""


class TestParseRaw:
    def test_full_round_trip(self, issue_comment_payload: dict) -> None:
        body = json.dumps(issue_comment_payload).encode()
        event = parse_raw("issue_comment", body)
        assert event is not None
        assert event.issue_number == 42

    def test_invalid_json(self) -> None:
        assert parse_raw("issue_comment", b"not json") is None

    def test_unknown_event(self) -> None:
        body = json.dumps({"action": "created"}).encode()
        assert parse_raw("deployment", body) is None
