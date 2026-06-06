"""Tests for opencode_github.github_client."""

from __future__ import annotations

import httpx
import pytest
import respx

from opencode_github.github_client import (
    GitHubAPIError,
    GitHubClient,
    IssueComment,
    PullRequest,
)

BASE = "https://api.github.com"


@pytest.fixture()
def mock_router() -> respx.MockRouter:
    with respx.mock(base_url=BASE, assert_all_called=False) as router:
        yield router


@pytest.fixture()
def client() -> GitHubClient:
    return GitHubClient(token="test-token", base_url=BASE, timeout=5)


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
