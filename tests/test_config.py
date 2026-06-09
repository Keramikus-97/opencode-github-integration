"""Tests for opencode_github.config."""

from __future__ import annotations

import pytest

from opencode_github.config import DEFAULT_TIMEOUT, MAX_TIMEOUT, MIN_TIMEOUT, Config


class TestConfigFromEnv:
    """Config.from_env – happy path and validation."""

    def test_minimal_env(self, minimal_env: dict[str, str]) -> None:
        cfg = Config.from_env(minimal_env)
        assert cfg.github_token == "ghp_test_token_123"
        assert cfg.anthropic_api_key == "sk-ant-test-key-456"
        assert cfg.model == "anthropic/claude-sonnet-4-20250514"
        assert cfg.github_api_url == "https://api.github.com"
        assert cfg.allowed_commands == ["/oc", "/opencode"]
        assert cfg.request_timeout == 30

    def test_custom_model(self, minimal_env: dict[str, str]) -> None:
        minimal_env["OPENCODE_MODEL"] = "anthropic/claude-haiku-3"
        cfg = Config.from_env(minimal_env)
        assert cfg.model == "anthropic/claude-haiku-3"

    def test_custom_api_url(self, minimal_env: dict[str, str]) -> None:
        minimal_env["GITHUB_API_URL"] = "https://ghe.corp.example.com/api/v3"
        cfg = Config.from_env(minimal_env)
        assert cfg.github_api_url == "https://ghe.corp.example.com/api/v3"

    def test_custom_commands(self, minimal_env: dict[str, str]) -> None:
        minimal_env["OPENCODE_COMMANDS"] = "/ai, /bot , /run"
        cfg = Config.from_env(minimal_env)
        assert cfg.allowed_commands == ["/ai", "/bot", "/run"]

    def test_custom_timeout(self, minimal_env: dict[str, str]) -> None:
        minimal_env["OPENCODE_TIMEOUT"] = "60"
        cfg = Config.from_env(minimal_env)
        assert cfg.request_timeout == 60

    def test_invalid_timeout_falls_back(self, minimal_env: dict[str, str]) -> None:
        minimal_env["OPENCODE_TIMEOUT"] = "not_a_number"
        cfg = Config.from_env(minimal_env)
        assert cfg.request_timeout == DEFAULT_TIMEOUT

    def test_negative_timeout_clamped(self, minimal_env: dict[str, str]) -> None:
        minimal_env["OPENCODE_TIMEOUT"] = "-5"
        cfg = Config.from_env(minimal_env)
        assert cfg.request_timeout == MIN_TIMEOUT

    def test_zero_timeout_clamped(self, minimal_env: dict[str, str]) -> None:
        minimal_env["OPENCODE_TIMEOUT"] = "0"
        cfg = Config.from_env(minimal_env)
        assert cfg.request_timeout == MIN_TIMEOUT

    def test_excessive_timeout_clamped(self, minimal_env: dict[str, str]) -> None:
        minimal_env["OPENCODE_TIMEOUT"] = "9999"
        cfg = Config.from_env(minimal_env)
        assert cfg.request_timeout == MAX_TIMEOUT

    def test_boundary_min_timeout(self, minimal_env: dict[str, str]) -> None:
        minimal_env["OPENCODE_TIMEOUT"] = str(MIN_TIMEOUT)
        cfg = Config.from_env(minimal_env)
        assert cfg.request_timeout == MIN_TIMEOUT

    def test_boundary_max_timeout(self, minimal_env: dict[str, str]) -> None:
        minimal_env["OPENCODE_TIMEOUT"] = str(MAX_TIMEOUT)
        cfg = Config.from_env(minimal_env)
        assert cfg.request_timeout == MAX_TIMEOUT

    def test_whitespace_stripped(self, minimal_env: dict[str, str]) -> None:
        minimal_env["GITHUB_TOKEN"] = "  token_with_spaces  "
        minimal_env["ANTHROPIC_API_KEY"] = "\tkey_with_tabs\t"
        cfg = Config.from_env(minimal_env)
        assert cfg.github_token == "token_with_spaces"
        assert cfg.anthropic_api_key == "key_with_tabs"

    def test_missing_github_token_raises(self) -> None:
        env = {"ANTHROPIC_API_KEY": "sk-key"}
        with pytest.raises(ValueError, match="GITHUB_TOKEN"):
            Config.from_env(env)

    def test_empty_github_token_raises(self) -> None:
        env = {"GITHUB_TOKEN": "  ", "ANTHROPIC_API_KEY": "sk-key"}
        with pytest.raises(ValueError, match="GITHUB_TOKEN"):
            Config.from_env(env)

    def test_missing_anthropic_key_raises(self) -> None:
        env = {"GITHUB_TOKEN": "ghp_tok"}
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            Config.from_env(env)

    def test_empty_anthropic_key_raises(self) -> None:
        env = {"GITHUB_TOKEN": "ghp_tok", "ANTHROPIC_API_KEY": ""}
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            Config.from_env(env)

    def test_uses_os_environ_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "env_tok")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env_key")
        cfg = Config.from_env()
        assert cfg.github_token == "env_tok"
        assert cfg.anthropic_api_key == "env_key"

    def test_empty_commands_string(self, minimal_env: dict[str, str]) -> None:
        minimal_env["OPENCODE_COMMANDS"] = "  ,  , "
        cfg = Config.from_env(minimal_env)
        assert cfg.allowed_commands == []


class TestConfigImmutability:
    def test_frozen(self, sample_config: Config) -> None:
        with pytest.raises(AttributeError):
            sample_config.github_token = "changed"  # type: ignore[misc]
