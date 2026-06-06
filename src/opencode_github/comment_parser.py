"""Parse GitHub comment payloads and extract commands."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedCommand:
    """A command extracted from a comment body."""

    trigger: str
    arguments: str
    raw_body: str


def extract_commands(body: str, allowed_triggers: list[str]) -> list[ParsedCommand]:
    """Return all recognised commands found in *body*.

    A command starts with one of the *allowed_triggers* at the beginning of a
    line (ignoring leading whitespace) and extends to the end of that line.

    Parameters
    ----------
    body:
        The full comment body (may be multi-line).
    allowed_triggers:
        Trigger prefixes to recognise, e.g. ``["/oc", "/opencode"]``.

    Returns
    -------
    list[ParsedCommand]
        Extracted commands in order of appearance.  Empty list when nothing
        matches.
    """
    if not body or not allowed_triggers:
        return []

    escaped = [re.escape(t) for t in sorted(allowed_triggers, key=len, reverse=True)]
    pattern = re.compile(
        r"^\s*(" + "|".join(escaped) + r")\b\s*(.*?)\s*$",
        re.MULTILINE,
    )

    results: list[ParsedCommand] = []
    for match in pattern.finditer(body):
        results.append(
            ParsedCommand(
                trigger=match.group(1),
                arguments=match.group(2),
                raw_body=body,
            )
        )
    return results


def is_command_comment(body: str, allowed_triggers: list[str]) -> bool:
    """Return ``True`` when *body* contains at least one recognised command."""
    return len(extract_commands(body, allowed_triggers)) > 0


def split_arguments(arguments: str) -> list[str]:
    """Split an argument string into tokens respecting double-quoted groups.

    >>> split_arguments('fix bug --verbose "hello world"')
    ['fix', 'bug', '--verbose', 'hello world']
    """
    tokens: list[str] = []
    current: list[str] = []
    in_quotes = False

    for char in arguments:
        if char == '"':
            in_quotes = not in_quotes
        elif char == " " and not in_quotes:
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(char)

    if current:
        tokens.append("".join(current))

    return tokens
