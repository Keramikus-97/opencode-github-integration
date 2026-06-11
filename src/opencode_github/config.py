"""Configuration loading for the OpenCode GitHub integration."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Config:
    """Immutable runtime configuration resolved from environment variables."""

    github_token: str
    anthropic_api_key: str
    model: str = "anthropic/claude-sonnet-4-20250514"
    github_api_url: str = "https://api.github.com"
    allowed_commands: list[str] = field(default_factory=lambda: ["/oc", "/opencode"])
    request_timeout: int = 30
    max_retries: int = 3
    backoff_factor: float = 0.5

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> Config:
        """Build a ``Config`` from environment variables.

        Parameters
        ----------
        environ:
            Mapping to read from.  Defaults to ``os.environ``.

        Raises
        ------
        ValueError
            If a required variable is missing or empty.
        """
        env = environ if environ is not None else dict(os.environ)

        github_token = env.get("GITHUB_TOKEN", "").strip()
        if not github_token:
            raise ValueError("GITHUB_TOKEN environment variable is required")

        anthropic_api_key = env.get("ANTHROPIC_API_KEY", "").strip()
        if not anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")

        model = env.get("OPENCODE_MODEL", "anthropic/claude-sonnet-4-20250514").strip()
        github_api_url = env.get("GITHUB_API_URL", "https://api.github.com").strip()

        allowed_raw = env.get("OPENCODE_COMMANDS", "/oc,/opencode").strip()
        allowed_commands = [cmd.strip() for cmd in allowed_raw.split(",") if cmd.strip()]

        timeout_raw = env.get("OPENCODE_TIMEOUT", "30").strip()
        try:
            request_timeout = int(timeout_raw)
        except ValueError:
            logger.warning(
                "Invalid OPENCODE_TIMEOUT value %r, falling back to 30 seconds",
                timeout_raw,
            )
            request_timeout = 30

        retries_raw = env.get("OPENCODE_MAX_RETRIES", "3").strip()
        try:
            max_retries = int(retries_raw)
        except ValueError:
            max_retries = 3
        max_retries = max(0, max_retries)

        backoff_raw = env.get("OPENCODE_BACKOFF_FACTOR", "0.5").strip()
        try:
            backoff_factor = float(backoff_raw)
        except ValueError:
            backoff_factor = 0.5
        if backoff_factor < 0:
            backoff_factor = 0.5

        return cls(
            github_token=github_token,
            anthropic_api_key=anthropic_api_key,
            model=model,
            github_api_url=github_api_url,
            allowed_commands=allowed_commands,
            request_timeout=request_timeout,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
        )
