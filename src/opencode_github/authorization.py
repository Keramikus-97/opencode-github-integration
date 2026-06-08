"""Author-permission gating for slash commands.

Prevents unauthorised users from triggering the OpenCode agent by
checking the commenter's repository permission level before processing
any extracted commands.
"""

from __future__ import annotations

from opencode_github.github_client import GitHubAPIError, GitHubClient
from opencode_github.webhook_handler import WebhookEvent

# GitHub permission levels in descending order of privilege.
_PERMISSION_RANK: dict[str, int] = {
    "admin": 4,
    "maintain": 3,
    "write": 2,
    "triage": 1,
    "read": 0,
    "none": -1,
}

DEFAULT_MIN_PERMISSION = "write"


def permission_rank(level: str) -> int:
    """Return a numeric rank for a GitHub permission level.

    Unknown levels are treated as ``"none"`` (rank ``-1``).
    """
    return _PERMISSION_RANK.get(level.lower(), -1)


def is_authorized(permission: str, min_level: str = DEFAULT_MIN_PERMISSION) -> bool:
    """Return ``True`` when *permission* meets or exceeds *min_level*."""
    return permission_rank(permission) >= permission_rank(min_level)


async def check_event_authorization(
    client: GitHubClient,
    event: WebhookEvent,
    min_level: str = DEFAULT_MIN_PERMISSION,
    post_denial: bool = True,
) -> bool:
    """Check whether the sender of *event* is authorized to run commands.

    Parameters
    ----------
    client:
        Authenticated GitHub API client.
    event:
        The parsed webhook event whose ``sender_login`` will be checked.
    min_level:
        Minimum required permission (default ``"write"``).
    post_denial:
        When ``True`` and the user is *not* authorized, post a polite
        comment explaining that the command was ignored.

    Returns
    -------
    bool
        ``True`` if the user has sufficient permissions.
    """
    try:
        permission = await client.get_user_permission(
            event.repo_owner, event.repo_name, event.sender_login
        )
    except GitHubAPIError:
        # If we cannot determine permission, deny by default.
        permission = "none"

    authorized = is_authorized(permission, min_level)

    if not authorized and post_denial:
        body = (
            f"@{event.sender_login} Sorry, you need **{min_level}** permission "
            f"(or higher) on this repository to use slash commands. "
            f"Your current permission level is **{permission}**."
        )
        try:
            await client.create_issue_comment(
                event.repo_owner, event.repo_name, event.issue_number, body
            )
        except GitHubAPIError:
            pass  # Best-effort; don't fail the whole flow.

    return authorized
