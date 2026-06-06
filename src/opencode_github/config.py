"""Environment-based configuration for OpenCode GitHub integration.

Delegates all env-var loading to ``utils.env`` and uses ``utils.errors``
for validation failures — no duplicated ``os.environ`` logic here.
"""

from __future__ import annotations

from dataclasses import dataclass

from opencode_github.utils.env import get_optional_env, get_required_env


@dataclass(frozen=True, slots=True)
class Config:
    """Validated runtime configuration."""

    github_token: str
    anthropic_api_key: str
    webhook_secret: str
    model: str
    github_api_url: str

    @classmethod
    def from_env(cls) -> Config:
        """Load and validate configuration from environment variables."""
        return cls(
            github_token=get_required_env("GITHUB_TOKEN"),
            anthropic_api_key=get_required_env("ANTHROPIC_API_KEY"),
            webhook_secret=get_required_env("WEBHOOK_SECRET"),
            model=get_optional_env(
                "OPENCODE_MODEL", "anthropic/claude-sonnet-4-20250514"
            ),
            github_api_url=get_optional_env(
                "GITHUB_API_URL", "https://api.github.com"
            ),
        )
