"""Real Slack adapter -- posts to a Slack Incoming Webhook.

Incoming Webhooks are the low-friction way to post into Slack: create a
Slack App in your own workspace (api.slack.com/apps -> Incoming Webhooks),
no app-review/approval needed for personal use, and Slack hands you a URL to
POST JSON to. That's a materially lower bar than the full Web API
(``chat.postMessage``), which needs a bot token and OAuth scopes -- the
friction the roadmap flagged as disproportionate for the signal it adds.

Trade-off: an Incoming Webhook is bound to one channel at creation time in
Slack's UI, so unlike ``MockSlackAdapter``, the ``channel`` argument here is
accepted for Protocol compatibility but isn't authoritative -- Slack posts to
whichever channel the webhook URL was configured for.
"""

from __future__ import annotations

import time

import httpx

_TIMEOUT = 10.0


class SlackAPIError(RuntimeError):
    """Raised when Slack's webhook endpoint returns an error response."""


class RealSlackAdapter:
    """Posts messages to a Slack Incoming Webhook URL."""

    def __init__(
        self,
        webhook_url: str,
        *,
        timeout: float = _TIMEOUT,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not webhook_url:
            raise ValueError("webhook_url is required")
        self._webhook_url = webhook_url
        self._client = httpx.Client(timeout=timeout, transport=transport)

    def post_message(self, channel: str, text: str) -> str:
        resp = self._client.post(self._webhook_url, json={"text": text})
        if resp.status_code >= 400:
            raise SlackAPIError(
                f"Slack webhook POST -> {resp.status_code}: {resp.text[:200]}"
            )
        # Incoming Webhooks just return the literal body "ok", not a message
        # timestamp/id the way chat.postMessage does -- synthesize a local one
        # so callers (Incident.slack_ts) still get something id-shaped.
        return f"webhook-{time.time():.6f}"

    def close(self) -> None:
        self._client.close()
