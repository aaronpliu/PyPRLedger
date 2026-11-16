"""HMAC signing for machine-to-machine write requests.

Git providers post review data without a user token, so those calls are
authenticated with a shared secret instead: a signature over the timestamp and
the raw request body, sent in ``X-Webhook-Signature``. The timestamp keeps a
captured request from being replayed later.
"""

from __future__ import annotations

import hashlib
import hmac
import time


TIMESTAMP_HEADER = "X-Webhook-Timestamp"
SIGNATURE_HEADER = "X-Webhook-Signature"

# How far the caller's clock may drift from ours before a request is rejected.
MAX_CLOCK_SKEW_SECONDS = 300


def compute_signature(secret: str, timestamp: str, body: bytes) -> str:
    """Return ``sha256=<hex>`` for the timestamp and body pair."""
    mac = hmac.new(secret.encode("utf-8"), timestamp.encode("utf-8") + b"." + body, hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


def verify_signature(
    secret: str,
    timestamp: str | None,
    signature: str | None,
    body: bytes,
    now: float | None = None,
) -> bool:
    """Check a signature, rejecting stale timestamps and malformed input."""
    if not secret or not timestamp or not signature:
        return False

    try:
        sent_at = int(timestamp)
    except (TypeError, ValueError):
        return False

    current = time.time() if now is None else now
    if abs(current - sent_at) > MAX_CLOCK_SKEW_SECONDS:
        return False

    expected = compute_signature(secret, timestamp, body)
    return hmac.compare_digest(expected, signature)
