"""Webhook signature verification.

Inbound webhook requests are trusted only if they carry a valid HMAC-SHA256
signature over the raw request body, keyed by ``SENTINEL_WEBHOOK_SECRET`` — the
same scheme GitHub itself uses for its webhooks (``X-Hub-Signature-256``).

When no secret is configured (the default), verification is skipped entirely so
the API stays easy to hit locally with zero setup, consistent with every other
real-integration credential in this project.
"""

from __future__ import annotations

import hashlib
import hmac

from fastapi import HTTPException, Request

from sentinel.config import Settings, get_settings

SIGNATURE_HEADER = "X-Sentinel-Signature-256"


def _expected_signature(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


async def verify_webhook_signature(
    request: Request, settings: Settings | None = None
) -> None:
    """FastAPI dependency: 401s unsigned/mis-signed requests when auth is enabled."""
    settings = settings or get_settings()
    if not settings.webhook_auth_enabled:
        return

    signature = request.headers.get(SIGNATURE_HEADER)
    if not signature:
        raise HTTPException(status_code=401, detail=f"Missing {SIGNATURE_HEADER} header")

    body = await request.body()
    expected = _expected_signature(settings.webhook_secret, body)
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
