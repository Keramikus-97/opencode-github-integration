"""GitHub webhook payload validation and event normalisation.

Delegates HMAC verification to ``utils.crypto``, input cleaning to
``utils.text``, and error types to ``utils.errors`` — avoiding duplicated
crypto / parsing boilerplate that would otherwise live in every handler.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from opencode_github.utils.crypto import compare_signatures, compute_hmac_sha256
from opencode_github.utils.errors import WebhookValidationError
from opencode_github.utils.text import sanitize_input


class EventType(Enum):
    """Supported GitHub webhook event types."""

    ISSUE_COMMENT = "issue_comment"
    PR_REVIEW_COMMENT = "pull_request_review_comment"
    UNKNOWN = "unknown"

    @classmethod
    def from_header(cls, header: str) -> EventType:
        """Map an ``X-GitHub-Event`` header value to an ``EventType``."""
        mapping: dict[str, EventType] = {
            "issue_comment": cls.ISSUE_COMMENT,
            "pull_request_review_comment": cls.PR_REVIEW_COMMENT,
        }
        return mapping.get(header.lower(), cls.UNKNOWN)


@dataclass(frozen=True, slots=True)
class WebhookEvent:
    """Normalised webhook event."""

    event_type: EventType
    action: str
    comment_body: str
    repo_full_name: str
    issue_number: int
    sender: str


def verify_signature(
    payload: str | bytes, secret: str, signature_header: str
) -> None:
    """Verify the ``X-Hub-Signature-256`` header against *payload*.

    Raises ``WebhookValidationError`` on mismatch.
    """
    expected = compute_hmac_sha256(secret, payload)
    actual = signature_header.removeprefix("sha256=")
    if not compare_signatures(expected, actual):
        raise WebhookValidationError(
            "Webhook signature verification failed",
            context={"expected_prefix": expected[:8]},
        )


def parse_event(event_header: str, payload: dict[str, Any]) -> WebhookEvent:
    """Parse a raw webhook *payload* into a ``WebhookEvent``."""
    event_type = EventType.from_header(event_header)
    action: str = payload.get("action", "")
    comment: dict[str, Any] = payload.get("comment", {})
    repo: dict[str, Any] = payload.get("repository", {})

    if "issue" in payload:
        issue_number: int = payload["issue"].get("number", 0)
    elif "pull_request" in payload:
        issue_number = payload["pull_request"].get("number", 0)
    else:
        issue_number = 0

    return WebhookEvent(
        event_type=event_type,
        action=action,
        comment_body=sanitize_input(comment.get("body", "")),
        repo_full_name=repo.get("full_name", ""),
        issue_number=issue_number,
        sender=comment.get("user", {}).get("login", ""),
    )
