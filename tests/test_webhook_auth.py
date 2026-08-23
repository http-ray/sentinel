"""Tests for HMAC webhook signature verification (sentinel/api/auth.py).

The auth dependency is exercised against a minimal, isolated FastAPI app (not
the real Sentinel app) so these tests stay hermetic: the real /webhook/alert
and /webhook/resolve endpoints run the full pipeline on a valid signature,
which would mean either mocking Orchestrator's internals here too or coupling
this file to that machinery. Two integration tests at the bottom confirm the
dependency is actually wired onto the real endpoints, checking only the
401-before-the-pipeline-runs case, which needs no adapters at all.
"""

from __future__ import annotations

import hashlib
import hmac

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from sentinel.api.auth import SIGNATURE_HEADER, verify_webhook_signature
from sentinel.config import Settings, get_settings

SECRET = "topsecret"
BODY = b'{"hello":"world"}'


def _sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


@pytest.fixture
def protected_client():
    """A throwaway app with one endpoint gated by the real auth dependency."""
    app = FastAPI()

    @app.post("/protected", dependencies=[Depends(verify_webhook_signature)])
    def _protected():
        return {"ok": True}

    return app


def _client_with_secret(app, secret: str) -> TestClient:
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, SENTINEL_WEBHOOK_SECRET=secret
    )
    return TestClient(app)


def test_auth_disabled_by_default_allows_unsigned_requests(protected_client):
    # No secret configured -> Settings(_env_file=None) defaults webhook_secret="".
    protected_client.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    client = TestClient(protected_client)

    resp = client.post("/protected", content=BODY)
    assert resp.status_code == 200


def test_missing_signature_header_is_rejected(protected_client):
    client = _client_with_secret(protected_client, SECRET)
    resp = client.post("/protected", content=BODY)
    assert resp.status_code == 401
    assert "Missing" in resp.json()["detail"]


def test_wrong_signature_is_rejected(protected_client):
    client = _client_with_secret(protected_client, SECRET)
    resp = client.post("/protected", content=BODY, headers={SIGNATURE_HEADER: "sha256=deadbeef"})
    assert resp.status_code == 401
    assert "Invalid" in resp.json()["detail"]


def test_signature_for_wrong_secret_is_rejected(protected_client):
    client = _client_with_secret(protected_client, SECRET)
    resp = client.post(
        "/protected", content=BODY, headers={SIGNATURE_HEADER: _sign("not-the-secret", BODY)}
    )
    assert resp.status_code == 401


def test_valid_signature_is_accepted(protected_client):
    client = _client_with_secret(protected_client, SECRET)
    resp = client.post(
        "/protected", content=BODY, headers={SIGNATURE_HEADER: _sign(SECRET, BODY)}
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_signature_is_over_the_exact_body_bytes(protected_client):
    # A signature computed for a different body must not validate this one.
    client = _client_with_secret(protected_client, SECRET)
    resp = client.post(
        "/protected", content=BODY, headers={SIGNATURE_HEADER: _sign(SECRET, b"different body")}
    )
    assert resp.status_code == 401


# -- Integration: confirm the dependency is actually wired onto the real app -- #


def test_real_alert_endpoint_rejects_unsigned_requests_when_auth_enabled():
    from sentinel.api.main import app

    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, SENTINEL_WEBHOOK_SECRET=SECRET
    )
    try:
        client = TestClient(app)
        resp = client.post("/webhook/alert", content=b"{}")
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_real_resolve_endpoint_rejects_unsigned_requests_when_auth_enabled():
    from sentinel.api.main import app

    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, SENTINEL_WEBHOOK_SECRET=SECRET
    )
    try:
        client = TestClient(app)
        resp = client.post("/webhook/resolve", content=b"{}")
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()
