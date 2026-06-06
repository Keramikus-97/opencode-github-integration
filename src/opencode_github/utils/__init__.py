"""Shared utilities for OpenCode GitHub integration.

This package centralises cross-cutting concerns — env loading, HTTP helpers,
cryptographic verification, text processing, and the exception hierarchy —
so that domain modules never duplicate this boilerplate.
"""

from opencode_github.utils.crypto import compare_signatures, compute_hmac_sha256
from opencode_github.utils.env import get_optional_env, get_required_env
from opencode_github.utils.errors import (
    CommandParseError,
    ConfigError,
    GitHubAPIError,
    OpenCodeError,
    WebhookValidationError,
)
from opencode_github.utils.http import (
    build_headers,
    create_http_client,
    parse_json_response,
)
from opencode_github.utils.text import extract_first_match, sanitize_input

__all__ = [
    "compare_signatures",
    "compute_hmac_sha256",
    "get_optional_env",
    "get_required_env",
    "CommandParseError",
    "ConfigError",
    "GitHubAPIError",
    "OpenCodeError",
    "WebhookValidationError",
    "build_headers",
    "create_http_client",
    "parse_json_response",
    "extract_first_match",
    "sanitize_input",
]
