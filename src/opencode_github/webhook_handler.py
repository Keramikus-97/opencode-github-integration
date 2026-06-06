"""Process incoming GitHub webhook payloads."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any


class EventType(Enum):
    """Supported GitHub webhook event types."""

    ISSUE_COMMENT = "issue_comment"
    PR_REVIEW_COMMENT = "pull_request_review_comment"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class WebhookEvent:
    """Parsed webhook event."""

    event_type: EventType
    action: str
    comment_body: str
    comment_id: int
    sender_login: str
    repo_owner: str
    repo_name: str
    issue_number: int
    raw_payload: dict[str, Any]


def classify_event(event_header: str) -> EventType:
    """Map a ``X-GitHub-Event`` header value to an ``EventType``."""
    try:
        return EventType(event_header)
    except ValueError:
        return EventType.UNKNOWN


def verify_signature(payload_body: bytes, signature: str, secret: str) -> bool:
    """Validate ``X-Hub-Signature-256`` against the shared webhook secret.

    Parameters
    ----------
    payload_body:
        Raw request body bytes.
    signature:
        Value of the ``X-Hub-Signature-256`` header (``sha256=…``).
    secret:
        The webhook secret configured on the repo.

    Returns
    -------
    bool
        ``True`` when the signature is valid.
    """
    if not signature or not secret:
        return False

    prefix = "sha256="
    if not signature.startswith(prefix):
        return False

    expected = hmac.new(
        secret.encode("utf-8"),
        payload_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature[len(prefix) :])


def parse_payload(event_type: EventType, payload: dict[str, Any]) -> WebhookEvent | None:
    """Convert a raw webhook JSON payload into a ``WebhookEvent``.

    Returns ``None`` for unsupported event types or payloads without the
    expected structure.
    """
    if event_type == EventType.UNKNOWN:
        return None

    action = payload.get("action", "")
    if action != "created":
        return None

    comment: dict[str, Any] | None = payload.get("comment")
    if comment is None:
        return None

    repo_data: dict[str, Any] = payload.get("repository", {})
    owner_data: dict[str, Any] = repo_data.get("owner", {})

    # For issue_comment events the issue number lives at payload.issue.number;
    # for PR review comments it lives at payload.pull_request.number.
    issue_number: int = 0
    if event_type == EventType.ISSUE_COMMENT:
        issue_number = payload.get("issue", {}).get("number", 0)
    elif event_type == EventType.PR_REVIEW_COMMENT:
        issue_number = payload.get("pull_request", {}).get("number", 0)

    return WebhookEvent(
        event_type=event_type,
        action=action,
        comment_body=comment.get("body", ""),
        comment_id=comment.get("id", 0),
        sender_login=comment.get("user", {}).get("login", ""),
        repo_owner=owner_data.get("login", ""),
        repo_name=repo_data.get("name", ""),
        issue_number=issue_number,
        raw_payload=payload,
    )


def parse_raw(event_header: str, body: bytes) -> WebhookEvent | None:
    """Convenience wrapper: classify, decode JSON, and parse in one call.

    .. warning::
        This function does NOT verify the webhook signature. Call
        :func:`verify_signature` before this or use :func:`parse_raw_verified`
        for a safe all-in-one path.
    """
    event_type = classify_event(event_header)
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return parse_payload(event_type, payload)


def parse_raw_verified(
    event_header: str,
    body: bytes,
    signature: str,
    secret: str,
) -> WebhookEvent | None:
    """Classify, verify signature, decode JSON, and parse — safe all-in-one path.

    Returns ``None`` if signature verification fails or the payload is
    unsupported/malformed.
    """
    if not verify_signature(body, signature, secret):
        return None
    return parse_raw(event_header, body)
