"""Shared environment-variable loading and validation.

Both ``config.py`` and any module that reads env vars (webhook secrets,
API keys) use these helpers instead of duplicating ``os.environ`` lookups
with ad-hoc validation scattered across the codebase.
"""

from __future__ import annotations

import os

from opencode_github.utils.errors import ConfigError


def get_required_env(name: str) -> str:
    """Return the value of a required environment variable.

    Raises ``ConfigError`` if the variable is unset or empty.
    """
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(
            f"Required environment variable {name!r} is not set",
            context={"variable": name},
        )
    return value


def get_optional_env(name: str, default: str = "") -> str:
    """Return the value of an optional environment variable, or *default*."""
    return os.environ.get(name, default).strip() or default
