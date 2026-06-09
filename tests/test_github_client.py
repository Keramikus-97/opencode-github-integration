"""Tests for opencode_github.github_client."""

from __future__ import annotations

import time
from collections.abc import Iterator

import httpx
import pytest
import respx

from opencode_github.github_client import (
    GitHubAPIError,
    GitHubClient,
    IssueComment,
    PullRequest,
    RateLimitError,
)

BASE = "https://api.github.com"


class RecordingSleep:
    """An async sleep stub that records requested delays without waiting."""

    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.calls.append(delay)


@pytest.fixture()
def mock_router() -> Iterator[respx.MockRouter]:
    with respx.mock(base_url=BASE, assert_all_called=False) as router:
        yield router


@pytest.fixture()
def sleep_stub() -> RecordingSleep:
    return RecordingSleep()


@pytest.fixture()
def client(sleep_stub: RecordingSleep) -> GitHubClient:
    return GitHubClient(token="test-token", base_url=BASE, timeout=5, sleep=sleep_stub)


class TestGetPullRequest:
    async def test_success(self, mock_router: respx.MockRouter, client: GitHubClient) -> None:
        mock_router.get("/repos/owner/repo/pulls/1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "number": 1,
                    "title": "My PR",
                    "head": {"ref": "feature"},
                    "base": {"ref": "main"},
                    "body": "Description",
                },
            )
        )
        pr = await client.get_pull_request("owner", "repo", 1)
        assert isinstance(pr, PullRequest)
        assert pr.number == 1
        assert pr.title == "My PR"
        assert pr.head_ref == "feature"
        assert pr.base_ref == "main"
        assert pr.body == "Description"

    async def test_null_body(self, mock_router: respx.MockRouter, client: GitHubClient) -> None:
        mock_router.get("/repos/owner/repo/pulls/2").mock(
            return_value=httpx.Response(
                200,
                json={
                    "number": 2,
                    "title": "No body",
                    "head": {"ref": "fix"},
                    "base": {"ref": "main"},
                    "body": None,
                },
            )
        )
        pr = await client.get_pull_request("owner", "repo", 2)
        assert pr.body == ""

    async def test_404_raises(self, mock_router: respx.MockRouter, client: GitHubClient) -> None:
        mock_router.get("/repos/owner/repo/pulls/999").mock(
            return_value=httpx.Response(404, json={"message": "Not Found"})
        )
        with pytest.raises(GitHubAPIError) as exc_info:
            await client.get_pull_request("owner", "repo", 999)
        assert exc_info.value.status_code == 404


class TestListIssueComments:
    async def test_success(self, mock_router: respx.MockRouter, client: GitHubClient) -> None:
        mock_router.get("/repos/owner/repo/issues/5/comments").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "id": 10,
                        "body": "hello",
                        "user": {"login": "alice"},
                        "html_url": "https://github.com/owner/repo/issues/5#issuecomment-10",
                    },
                    {
                        "id": 11,
                        "body": None,
                        "user": {"login": "bob"},
                        "html_url": "https://github.com/owner/repo/issues/5#issuecomment-11",
                    },
                ],
            )
        )
        comments = await client.list_issue_comments("owner", "repo", 5)
        assert len(comments) == 2
        assert comments[0] == IssueComment(
            id=10,
            body="hello",
            user_login="alice",
            html_url="https://github.com/owner/repo/issues/5#issuecomment-10",
        )
        assert comments[1].body == ""


class TestCreateIssueComment:
    async def test_success(self, mock_router: respx.MockRouter, client: GitHubClient) -> None:
        mock_router.post("/repos/owner/repo/issues/5/comments").mock(
            return_value=httpx.Response(
                201,
                json={
                    "id": 20,
                    "body": "posted!",
                    "user": {"login": "bot"},
                    "html_url": "https://github.com/owner/repo/issues/5#issuecomment-20",
                },
            )
        )
        comment = await client.create_issue_comment("owner", "repo", 5, "posted!")
        assert comment.id == 20
        assert comment.body == "posted!"


class TestAddReaction:
    async def test_success(self, mock_router: respx.MockRouter, client: GitHubClient) -> None:
        mock_router.post("/repos/owner/repo/issues/comments/10/reactions").mock(
            return_value=httpx.Response(201, json={"id": 1, "content": "+1"})
        )
        await client.add_reaction("owner", "repo", 10)

    async def test_server_error(self, mock_router: respx.MockRouter, client: GitHubClient) -> None:
        mock_router.post("/repos/owner/repo/issues/comments/10/reactions").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        with pytest.raises(GitHubAPIError) as exc_info:
            await client.add_reaction("owner", "repo", 10)
        assert exc_info.value.status_code == 500


class TestGetRepo:
    async def test_success(self, mock_router: respx.MockRouter, client: GitHubClient) -> None:
        mock_router.get("/repos/owner/repo").mock(
            return_value=httpx.Response(200, json={"full_name": "owner/repo", "private": False})
        )
        data = await client.get_repo("owner", "repo")
        assert data["full_name"] == "owner/repo"


class TestContextManager:
    async def test_async_with(self) -> None:
        async with GitHubClient(token="tok") as c:
            assert c._token == "tok"


class TestRetryAndRateLimit:
    async def test_success_first_try_no_sleep(
        self,
        mock_router: respx.MockRouter,
        client: GitHubClient,
        sleep_stub: RecordingSleep,
    ) -> None:
        mock_router.get("/repos/owner/repo").mock(
            return_value=httpx.Response(200, json={"full_name": "owner/repo"})
        )
        data = await client.get_repo("owner", "repo")
        assert data["full_name"] == "owner/repo"
        assert sleep_stub.calls == []

    async def test_retries_5xx_then_succeeds(
        self,
        mock_router: respx.MockRouter,
        client: GitHubClient,
        sleep_stub: RecordingSleep,
    ) -> None:
        route = mock_router.get("/repos/owner/repo")
        route.side_effect = [
            httpx.Response(503, text="unavailable"),
            httpx.Response(502, text="bad gateway"),
            httpx.Response(200, json={"full_name": "owner/repo"}),
        ]
        data = await client.get_repo("owner", "repo")
        assert data["full_name"] == "owner/repo"
        assert len(sleep_stub.calls) == 2
        assert all(delay > 0 for delay in sleep_stub.calls)

    async def test_5xx_exhausts_retries_and_raises(
        self,
        mock_router: respx.MockRouter,
        client: GitHubClient,
        sleep_stub: RecordingSleep,
    ) -> None:
        mock_router.get("/repos/owner/repo").mock(
            return_value=httpx.Response(500, text="boom")
        )
        with pytest.raises(GitHubAPIError) as exc_info:
            await client.get_repo("owner", "repo")
        assert exc_info.value.status_code == 500
        # default max_retries=3 → 4 attempts → 3 sleeps
        assert len(sleep_stub.calls) == 3

    async def test_4xx_not_retried(
        self,
        mock_router: respx.MockRouter,
        client: GitHubClient,
        sleep_stub: RecordingSleep,
    ) -> None:
        mock_router.get("/repos/owner/repo/pulls/1").mock(
            return_value=httpx.Response(404, json={"message": "Not Found"})
        )
        with pytest.raises(GitHubAPIError) as exc_info:
            await client.get_pull_request("owner", "repo", 1)
        assert exc_info.value.status_code == 404
        assert sleep_stub.calls == []

    async def test_429_retries_then_succeeds(
        self,
        mock_router: respx.MockRouter,
        client: GitHubClient,
        sleep_stub: RecordingSleep,
    ) -> None:
        route = mock_router.get("/repos/owner/repo")
        route.side_effect = [
            httpx.Response(429, text="slow down"),
            httpx.Response(200, json={"full_name": "owner/repo"}),
        ]
        data = await client.get_repo("owner", "repo")
        assert data["full_name"] == "owner/repo"
        assert len(sleep_stub.calls) == 1

    async def test_429_exhausted_raises_rate_limit_error(
        self,
        mock_router: respx.MockRouter,
        client: GitHubClient,
    ) -> None:
        mock_router.get("/repos/owner/repo").mock(
            return_value=httpx.Response(
                429,
                text="rate limited",
                headers={"retry-after": "7", "x-ratelimit-reset": "1700000000"},
            )
        )
        with pytest.raises(RateLimitError) as exc_info:
            await client.get_repo("owner", "repo")
        assert exc_info.value.status_code == 429
        assert exc_info.value.retry_after == 7.0
        assert exc_info.value.reset_at == 1700000000.0

    async def test_retry_after_header_honored(
        self,
        mock_router: respx.MockRouter,
        client: GitHubClient,
        sleep_stub: RecordingSleep,
    ) -> None:
        route = mock_router.get("/repos/owner/repo")
        route.side_effect = [
            httpx.Response(429, headers={"retry-after": "4"}, text="wait"),
            httpx.Response(200, json={"full_name": "owner/repo"}),
        ]
        await client.get_repo("owner", "repo")
        assert sleep_stub.calls == [4.0]

    async def test_403_with_remaining_zero_is_rate_limited(
        self,
        mock_router: respx.MockRouter,
        client: GitHubClient,
        sleep_stub: RecordingSleep,
    ) -> None:
        route = mock_router.get("/repos/owner/repo")
        route.side_effect = [
            httpx.Response(403, headers={"x-ratelimit-remaining": "0"}, text="limit"),
            httpx.Response(200, json={"full_name": "owner/repo"}),
        ]
        data = await client.get_repo("owner", "repo")
        assert data["full_name"] == "owner/repo"
        assert len(sleep_stub.calls) == 1

    async def test_403_reset_header_drives_delay(
        self,
        mock_router: respx.MockRouter,
        client: GitHubClient,
        sleep_stub: RecordingSleep,
    ) -> None:
        reset_at = time.time() + 5
        route = mock_router.get("/repos/owner/repo")
        route.side_effect = [
            httpx.Response(
                403,
                headers={
                    "x-ratelimit-remaining": "0",
                    "x-ratelimit-reset": str(int(reset_at)),
                },
                text="limit",
            ),
            httpx.Response(200, json={"full_name": "owner/repo"}),
        ]
        await client.get_repo("owner", "repo")
        assert len(sleep_stub.calls) == 1
        assert 0 < sleep_stub.calls[0] <= 6

    async def test_403_with_retry_after_only_is_rate_limited(
        self,
        mock_router: respx.MockRouter,
        client: GitHubClient,
        sleep_stub: RecordingSleep,
    ) -> None:
        route = mock_router.get("/repos/owner/repo")
        route.side_effect = [
            httpx.Response(403, headers={"retry-after": "3"}, text="secondary"),
            httpx.Response(200, json={"full_name": "owner/repo"}),
        ]
        await client.get_repo("owner", "repo")
        assert sleep_stub.calls == [3.0]

    async def test_rate_limit_error_with_invalid_headers_has_none_fields(
        self,
        mock_router: respx.MockRouter,
        client: GitHubClient,
    ) -> None:
        mock_router.get("/repos/owner/repo").mock(
            return_value=httpx.Response(
                429,
                text="rate limited",
                headers={"retry-after": "soon", "x-ratelimit-reset": "later"},
            )
        )
        with pytest.raises(RateLimitError) as exc_info:
            await client.get_repo("owner", "repo")
        assert exc_info.value.retry_after is None
        assert exc_info.value.reset_at is None

    async def test_204_returns_none(
        self,
        mock_router: respx.MockRouter,
        client: GitHubClient,
    ) -> None:
        mock_router.post("/repos/owner/repo/issues/comments/9/reactions").mock(
            return_value=httpx.Response(204)
        )
        result = await client.add_reaction("owner", "repo", 9)
        assert result is None

    async def test_403_without_rate_limit_signal_not_retried(
        self,
        mock_router: respx.MockRouter,
        client: GitHubClient,
        sleep_stub: RecordingSleep,
    ) -> None:
        mock_router.get("/repos/owner/repo").mock(
            return_value=httpx.Response(403, text="forbidden")
        )
        with pytest.raises(GitHubAPIError) as exc_info:
            await client.get_repo("owner", "repo")
        assert exc_info.value.status_code == 403
        assert not isinstance(exc_info.value, RateLimitError)
        assert sleep_stub.calls == []

    async def test_transport_error_retried_then_succeeds(
        self,
        mock_router: respx.MockRouter,
        client: GitHubClient,
        sleep_stub: RecordingSleep,
    ) -> None:
        route = mock_router.get("/repos/owner/repo")
        route.side_effect = [
            httpx.ConnectError("boom"),
            httpx.Response(200, json={"full_name": "owner/repo"}),
        ]
        data = await client.get_repo("owner", "repo")
        assert data["full_name"] == "owner/repo"
        assert len(sleep_stub.calls) == 1

    async def test_transport_error_exhausted_reraises(
        self,
        mock_router: respx.MockRouter,
        sleep_stub: RecordingSleep,
    ) -> None:
        client = GitHubClient(
            token="t", base_url=BASE, max_retries=1, sleep=sleep_stub
        )
        mock_router.get("/repos/owner/repo").mock(side_effect=httpx.ConnectError("down"))
        with pytest.raises(httpx.ConnectError):
            await client.get_repo("owner", "repo")
        assert len(sleep_stub.calls) == 1

    async def test_max_retries_zero_disables_retry(
        self,
        mock_router: respx.MockRouter,
        sleep_stub: RecordingSleep,
    ) -> None:
        client = GitHubClient(token="t", base_url=BASE, max_retries=0, sleep=sleep_stub)
        mock_router.get("/repos/owner/repo").mock(
            return_value=httpx.Response(500, text="boom")
        )
        with pytest.raises(GitHubAPIError):
            await client.get_repo("owner", "repo")
        assert sleep_stub.calls == []

    async def test_backoff_factor_caps_at_max_backoff(self) -> None:
        client = GitHubClient(
            token="t", backoff_factor=1000.0, max_backoff=2.0, sleep=None
        )
        assert client._backoff_delay(5) == 2.0

    async def test_invalid_retry_after_falls_back_to_backoff(
        self,
        mock_router: respx.MockRouter,
        client: GitHubClient,
        sleep_stub: RecordingSleep,
    ) -> None:
        route = mock_router.get("/repos/owner/repo")
        route.side_effect = [
            httpx.Response(429, headers={"retry-after": "soon"}, text="wait"),
            httpx.Response(200, json={"full_name": "owner/repo"}),
        ]
        await client.get_repo("owner", "repo")
        assert len(sleep_stub.calls) == 1
        assert sleep_stub.calls[0] > 0


class TestFromConfig:
    def test_threads_config_values(self) -> None:
        from opencode_github.config import Config

        cfg = Config.from_env(
            {
                "GITHUB_TOKEN": "tok",
                "ANTHROPIC_API_KEY": "key",
                "GITHUB_API_URL": "https://ghe.example.com/api/v3",
                "OPENCODE_TIMEOUT": "12",
                "OPENCODE_MAX_RETRIES": "5",
                "OPENCODE_BACKOFF_FACTOR": "1.5",
            }
        )
        client = GitHubClient.from_config(cfg)
        assert client._base_url == "https://ghe.example.com/api/v3"
        assert client._max_retries == 5
        assert client._backoff_factor == 1.5
