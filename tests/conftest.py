"""Shared fixtures for the test suite."""

from __future__ import annotations

import pytest

from opencode_github.config import Config


@pytest.fixture()
def minimal_env() -> dict[str, str]:
    """Minimal valid environment for ``Config.from_env``."""
    return {
        "GITHUB_TOKEN": "ghp_test_token_123",
        "ANTHROPIC_API_KEY": "sk-ant-test-key-456",
    }


@pytest.fixture()
def sample_config(minimal_env: dict[str, str]) -> Config:
    return Config.from_env(minimal_env)


@pytest.fixture()
def issue_comment_payload() -> dict:
    """A realistic ``issue_comment`` webhook payload."""
    return {
        "action": "created",
        "issue": {"number": 42},
        "comment": {
            "id": 1001,
            "body": "/oc fix the typo in README",
            "user": {"login": "contributor"},
            "html_url": "https://github.com/owner/repo/issues/42#issuecomment-1001",
        },
        "repository": {
            "name": "repo",
            "owner": {"login": "owner"},
        },
    }


@pytest.fixture()
def pr_review_comment_payload() -> dict:
    """A realistic ``pull_request_review_comment`` webhook payload."""
    return {
        "action": "created",
        "pull_request": {"number": 7},
        "comment": {
            "id": 2002,
            "body": "/opencode refactor this function",
            "user": {"login": "reviewer"},
            "html_url": "https://github.com/owner/repo/pull/7#discussion_r2002",
        },
        "repository": {
            "name": "repo",
            "owner": {"login": "owner"},
        },
    }
