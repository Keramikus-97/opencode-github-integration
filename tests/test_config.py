"""Tests for the Config dataclass."""

from __future__ import annotations

import pytest

from opencode_github.config import Config
from opencode_github.utils.errors import ConfigError


class TestConfigFromEnv:
    def test_loads_all_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("WEBHOOK_SECRET", "whsec_test")
        monkeypatch.delenv("OPENCODE_MODEL", raising=False)
        monkeypatch.delenv("GITHUB_API_URL", raising=False)

        cfg = Config.from_env()

        assert cfg.github_token == "ghp_test"
        assert cfg.anthropic_api_key == "sk-ant-test"
        assert cfg.webhook_secret == "whsec_test"
        assert cfg.model == "anthropic/claude-sonnet-4-20250514"
        assert cfg.github_api_url == "https://api.github.com"

    def test_overrides_optionals(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "t")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
        monkeypatch.setenv("WEBHOOK_SECRET", "s")
        monkeypatch.setenv("OPENCODE_MODEL", "custom/model")
        monkeypatch.setenv("GITHUB_API_URL", "https://ghes.example.com/api/v3")

        cfg = Config.from_env()

        assert cfg.model == "custom/model"
        assert cfg.github_api_url == "https://ghes.example.com/api/v3"

    def test_raises_on_missing_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("WEBHOOK_SECRET", raising=False)

        with pytest.raises(ConfigError, match="GITHUB_TOKEN"):
            Config.from_env()
