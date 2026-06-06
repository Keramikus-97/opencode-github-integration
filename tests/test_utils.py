"""Tests for shared utility modules."""

from __future__ import annotations

import pytest

from opencode_github.utils.crypto import compare_signatures, compute_hmac_sha256
from opencode_github.utils.env import get_optional_env, get_required_env
from opencode_github.utils.errors import (
    CommandParseError,
    ConfigError,
    GitHubAPIError,
    OpenCodeError,
    WebhookValidationError,
)
from opencode_github.utils.text import extract_first_match, sanitize_input

# --- errors ---


class TestErrorHierarchy:
    def test_all_errors_inherit_from_opencode_error(self) -> None:
        error_classes = (
            ConfigError,
            GitHubAPIError,
            WebhookValidationError,
            CommandParseError,
        )
        for cls in error_classes:
            assert issubclass(cls, OpenCodeError)

    def test_opencode_error_stores_context(self) -> None:
        err = OpenCodeError("boom", context={"key": "val"})
        assert str(err) == "boom"
        assert err.context == {"key": "val"}

    def test_github_api_error_stores_status_code(self) -> None:
        err = GitHubAPIError("not found", status_code=404)
        assert err.status_code == 404


# --- env ---


class TestGetRequiredEnv:
    def test_returns_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_VAR", "hello")
        assert get_required_env("TEST_VAR") == "hello"

    def test_raises_on_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TEST_VAR", raising=False)
        with pytest.raises(ConfigError, match="TEST_VAR"):
            get_required_env("TEST_VAR")

    def test_raises_on_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_VAR", "   ")
        with pytest.raises(ConfigError):
            get_required_env("TEST_VAR")


class TestGetOptionalEnv:
    def test_returns_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPT", "world")
        assert get_optional_env("OPT", "fallback") == "world"

    def test_returns_default_when_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OPT", raising=False)
        assert get_optional_env("OPT", "fallback") == "fallback"

    def test_returns_default_when_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPT", "  ")
        assert get_optional_env("OPT", "fallback") == "fallback"


# --- crypto ---


class TestHmac:
    def test_compute_and_compare(self) -> None:
        sig = compute_hmac_sha256("secret", "payload")
        assert isinstance(sig, str)
        assert len(sig) == 64  # hex sha256
        assert compare_signatures(sig, sig)

    def test_compare_case_insensitive(self) -> None:
        sig = compute_hmac_sha256("s", "p")
        assert compare_signatures(sig.upper(), sig.lower())

    def test_mismatch(self) -> None:
        assert not compare_signatures("aabb", "ccdd")

    def test_accepts_bytes(self) -> None:
        sig = compute_hmac_sha256(b"key", b"data")
        assert len(sig) == 64


# --- text ---


class TestExtractFirstMatch:
    def test_finds_match(self) -> None:
        assert extract_first_match(r"\d+", "abc 42 def") == "42"

    def test_returns_none_on_no_match(self) -> None:
        assert extract_first_match(r"\d+", "no digits") is None

    def test_accepts_compiled_pattern(self) -> None:
        import re

        pat = re.compile(r"hello", re.IGNORECASE)
        assert extract_first_match(pat, "say HELLO world") == "HELLO"


class TestSanitizeInput:
    def test_strips_control_chars(self) -> None:
        assert sanitize_input("a\x00b\x01c") == "abc"

    def test_preserves_normal_whitespace(self) -> None:
        assert sanitize_input("hello\nworld\ttab") == "hello\nworld\ttab"

    def test_truncates(self) -> None:
        assert sanitize_input("abcdef", max_length=3) == "abc"
