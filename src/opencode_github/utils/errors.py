"""Shared exception hierarchy for OpenCode GitHub integration.

Without this module, each domain module (config, github_client,
webhook_handler, comment_parser) would define its own ad-hoc exception
classes, leading to duplicated error-handling boilerplate and inconsistent
error types.
"""

from __future__ import annotations


class OpenCodeError(Exception):
    """Base exception for all OpenCode errors."""

    def __init__(
        self, message: str, *, context: dict[str, object] | None = None
    ) -> None:
        super().__init__(message)
        self.context = context or {}


class ConfigError(OpenCodeError):
    """Raised when configuration is missing or invalid."""


class GitHubAPIError(OpenCodeError):
    """Raised when a GitHub API request fails."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        context: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message, context=context)
        self.status_code = status_code


class WebhookValidationError(OpenCodeError):
    """Raised when webhook payload validation fails."""


class CommandParseError(OpenCodeError):
    """Raised when a slash command cannot be parsed."""
