"""Configuration loading for the OpenCode GitHub integration."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

MIN_TIMEOUT = 1
MAX_TIMEOUT = 300
DEFAULT_TIMEOUT = 30


@dataclass(frozen=True)
class Config:
    """Immutable runtime configuration resolved from environment variables."""

    github_token: str
    anthropic_api_key: str
    model: str = "anthropic/claude-sonnet-4-20250514"
    github_api_url: str = "https://api.github.com"
    allowed_commands: list[str] = field(default_factory=lambda: ["/oc", "/opencode"])
    request_timeout: int = 30

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

        timeout_raw = env.get("OPENCODE_TIMEOUT", str(DEFAULT_TIMEOUT)).strip()
        try:
            request_timeout = int(timeout_raw)
        except ValueError:
            logger.warning(
                "Invalid OPENCODE_TIMEOUT value %r, falling back to %d",
                timeout_raw,
                DEFAULT_TIMEOUT,
            )
            request_timeout = DEFAULT_TIMEOUT

        if request_timeout < MIN_TIMEOUT or request_timeout > MAX_TIMEOUT:
            logger.warning(
                "OPENCODE_TIMEOUT=%d out of range [%d, %d], clamping",
                request_timeout,
                MIN_TIMEOUT,
                MAX_TIMEOUT,
            )
            request_timeout = max(MIN_TIMEOUT, min(request_timeout, MAX_TIMEOUT))

        return cls(
            github_token=github_token,
            anthropic_api_key=anthropic_api_key,
            model=model,
            github_api_url=github_api_url,
            allowed_commands=allowed_commands,
            request_timeout=request_timeout,
        )
