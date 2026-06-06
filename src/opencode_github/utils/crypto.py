"""HMAC-SHA256 signature utilities.

Used by ``webhook_handler`` for payload validation and potentially by any
future module that needs message authentication.  Centralising the crypto
logic avoids duplicating hmac / hashlib boilerplate.
"""

from __future__ import annotations

import hashlib
import hmac


def compute_hmac_sha256(secret: str | bytes, payload: str | bytes) -> str:
    """Compute an HMAC-SHA256 hex digest for *payload* using *secret*."""
    if isinstance(secret, str):
        secret = secret.encode()
    if isinstance(payload, str):
        payload = payload.encode()
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def compare_signatures(expected: str, actual: str) -> bool:
    """Constant-time comparison of two hex-encoded signatures."""
    return hmac.compare_digest(expected.lower(), actual.lower())
