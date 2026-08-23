"""Tests for the real Slack adapter.

HTTP calls are faked via ``httpx.MockTransport`` so the suite stays fully
offline, consistent with the rest of Sentinel's tests -- no real network
call is made anywhere in this file.
"""

from __future__ import annotations

import json

import httpx
import pytest

from sentinel.adapters.slack_real import RealSlackAdapter, SlackAPIError

WEBHOOK_URL = "https://hooks.slack.com/services/T000/B000/xxxxxxxxxxxxxxxxxxxxxxxx"


def _adapter(handler) -> RealSlackAdapter:
    return RealSlackAdapter(WEBHOOK_URL, transport=httpx.MockTransport(handler))


def test_webhook_url_is_required():
    with pytest.raises(ValueError):
        RealSlackAdapter("")


def test_post_message_sends_text_and_returns_an_id():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text="ok")

    adapter = _adapter(handler)
    ts = adapter.post_message("#incidents", "*SEV2* checkout down")

    assert len(seen) == 1
    assert seen[0].url == WEBHOOK_URL
    assert json_body(seen[0]) == {"text": "*SEV2* checkout down"}
    assert ts.startswith("webhook-")


def test_post_message_raises_on_error_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="no_service")

    adapter = _adapter(handler)
    with pytest.raises(SlackAPIError):
        adapter.post_message("#incidents", "hello")


def json_body(request: httpx.Request) -> dict:
    return json.loads(request.content)
