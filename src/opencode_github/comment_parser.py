"""Slash-command extraction from GitHub comment bodies.

Uses ``utils.text`` for regex matching and ``utils.errors`` for parse
failures — no ad-hoc regex or exception boilerplate duplicated here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from opencode_github.utils.text import extract_first_match, sanitize_input

_TRIGGER_PATTERN = re.compile(r"^(/oc|/opencode)\b", re.MULTILINE)
_ARGS_PATTERN = re.compile(r"^(?:/oc|/opencode)\s+(.*)", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class ParsedCommand:
    """A parsed slash command extracted from a comment body."""

    trigger: str
    arguments: str


def parse_command(body: str) -> ParsedCommand | None:
    """Extract the first slash command from a comment *body*.

    Returns ``None`` when *body* contains no recognised trigger.
    """
    if not body or not body.strip():
        return None

    cleaned = sanitize_input(body)
    trigger = extract_first_match(_TRIGGER_PATTERN, cleaned)
    if trigger is None:
        return None

    args_match = re.search(_ARGS_PATTERN, cleaned)
    arguments = args_match.group(1).strip() if args_match else ""

    return ParsedCommand(trigger=trigger, arguments=arguments)


def is_trigger(body: str) -> bool:
    """Return ``True`` if *body* contains a recognised slash-command trigger."""
    return parse_command(body) is not None
