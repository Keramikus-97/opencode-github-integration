"""Shared text / regex utilities.

Used by ``comment_parser`` for slash-command extraction and by any module
that needs pattern matching or input sanitisation.  Factoring these out
prevents each module from writing its own one-off regex helpers.
"""

from __future__ import annotations

import re


def extract_first_match(pattern: str | re.Pattern[str], text: str) -> str | None:
    """Return the first regex match (group 0) in *text*, or ``None``."""
    compiled = re.compile(pattern) if isinstance(pattern, str) else pattern
    match = compiled.search(text)
    return match.group(0) if match else None


def sanitize_input(text: str, *, max_length: int = 10_000) -> str:
    """Strip control characters and truncate *text* to *max_length*."""
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return cleaned[:max_length]
