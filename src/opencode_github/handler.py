"""End-to-end webhook processing that ties all components together."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from opencode_github.comment_parser import ParsedCommand, extract_commands
from opencode_github.config import Config
from opencode_github.github_client import GitHubClient
from opencode_github.webhook_handler import WebhookEvent, parse_raw, verify_signature

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HandlerResult:
    """Outcome of processing a single webhook delivery."""

    event: WebhookEvent | None
    commands: list[ParsedCommand] = field(default_factory=list)
    acknowledged: bool = False
    skipped_reason: str = ""


class WebhookProcessor:
    """Orchestrate signature verification, payload parsing, and command extraction.

    Parameters
    ----------
    config:
        Runtime configuration (tokens, allowed commands, etc.).
    webhook_secret:
        Optional shared secret for verifying ``X-Hub-Signature-256``.
        When ``None`` signature verification is skipped.
    ignore_logins:
        Set of login names whose comments should be ignored (bot-loop prevention).
        Typically includes the bot's own login so it doesn't respond to itself.
    """

    def __init__(
        self,
        config: Config,
        webhook_secret: str | None = None,
        ignore_logins: set[str] | None = None,
    ) -> None:
        self._config = config
        self._webhook_secret = webhook_secret
        self._ignore_logins: set[str] = ignore_logins or set()
        self._client = GitHubClient(
            token=config.github_token,
            base_url=config.github_api_url,
            timeout=config.request_timeout,
        )

    async def close(self) -> None:
        await self._client.close()

    async def __aenter__(self) -> WebhookProcessor:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def process(
        self,
        event_header: str,
        body: bytes,
        signature: str | None = None,
    ) -> HandlerResult:
        """Process a raw webhook delivery.

        Parameters
        ----------
        event_header:
            Value of the ``X-GitHub-Event`` request header.
        body:
            Raw request body bytes.
        signature:
            Value of the ``X-Hub-Signature-256`` header, if present.

        Returns
        -------
        HandlerResult
        """
        if self._webhook_secret:
            if not signature or not verify_signature(body, signature, self._webhook_secret):
                logger.warning("Webhook signature verification failed")
                return HandlerResult(event=None, skipped_reason="invalid_signature")

        event = parse_raw(event_header, body)
        if event is None:
            return HandlerResult(event=None, skipped_reason="unsupported_event")

        if event.sender_login in self._ignore_logins:
            logger.debug("Ignoring comment from %s (bot-loop prevention)", event.sender_login)
            return HandlerResult(event=event, skipped_reason="ignored_login")

        commands = extract_commands(event.comment_body, self._config.allowed_commands)
        if not commands:
            return HandlerResult(event=event, skipped_reason="no_commands")

        await self._acknowledge(event)

        return HandlerResult(event=event, commands=commands, acknowledged=True)

    async def _acknowledge(self, event: WebhookEvent) -> None:
        """Add a reaction to the triggering comment so the user knows we saw it."""
        try:
            await self._client.add_reaction(
                event.repo_owner,
                event.repo_name,
                event.comment_id,
                reaction="eyes",
            )
        except Exception:
            logger.debug("Failed to add acknowledgement reaction", exc_info=True)
