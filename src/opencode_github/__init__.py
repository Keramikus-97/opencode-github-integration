"""OpenCode GitHub integration helpers."""

from opencode_github.comment_parser import (
    ParsedCommand,
    extract_commands,
    is_command_comment,
    split_arguments,
)
from opencode_github.config import Config
from opencode_github.github_client import (
    GitHubAPIError,
    GitHubClient,
    IssueComment,
    PullRequest,
)
from opencode_github.handler import HandlerResult, WebhookProcessor
from opencode_github.webhook_handler import (
    EventType,
    WebhookEvent,
    classify_event,
    parse_payload,
    parse_raw,
    verify_signature,
)

__all__ = [
    "Config",
    "EventType",
    "GitHubAPIError",
    "GitHubClient",
    "HandlerResult",
    "IssueComment",
    "ParsedCommand",
    "PullRequest",
    "WebhookEvent",
    "WebhookProcessor",
    "classify_event",
    "extract_commands",
    "is_command_comment",
    "parse_payload",
    "parse_raw",
    "split_arguments",
    "verify_signature",
]
