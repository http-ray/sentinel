"""Integration tests for the ACK-immediately-then-background webhook flow.

These hit the real /webhook/alert, /webhook/resolve, and /incidents endpoints
via TestClient, with get_settings/get_orchestrator/get_store overridden so the
pipeline runs against mocks and stays offline (same pattern as
test_webhook_auth.py's real-endpoint checks). Starlette's TestClient runs
background tasks to completion before a call returns, so "poll GET
afterward" is exercised as a second, separate request rather than a race --
what's actually being proven is (a) the POST response reflects the
pre-enrichment incident, and (b) the background task's work was actually
persisted, not merely that it eventually runs.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from sentinel.adapters import get_adapters
from sentinel.api.main import app, get_orchestrator
from sentinel.config import Settings, get_settings
from sentinel.llm import LLMClient
from sentinel.pipeline.orchestrator import Orchestrator
from sentinel.store import get_store
from sentinel.store.incidents import IncidentStore


class _DisabledLLM(LLMClient):
    @property
    def enabled(self) -> bool:
        return False


@pytest.fixture
def client():
    settings = Settings(_env_file=None)  # blank webhook secret -> auth disabled
    store = IncidentStore()
    orch = Orchestrator(adapters=get_adapters(settings), store=store, llm=_DisabledLLM())

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_orchestrator] = lambda: orch
    app.dependency_overrides[get_store] = lambda: store
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _post(client, path, payload):
    return client.post(path, content=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})


def test_ingest_alert_acks_before_enrichment(client, checkout_alert):
    resp = _post(client, "/webhook/alert", checkout_alert.model_dump(mode="json"))

    assert resp.status_code == 202
    body = resp.json()
    assert body["suspects"] == []
    assert body["brief"] is None
    assert [e["label"] for e in body["timeline"]] == ["detected"]


def test_ingest_alert_background_task_persists_full_enrichment(client, checkout_alert):
    resp = _post(client, "/webhook/alert", checkout_alert.model_dump(mode="json"))
    incident_id = resp.json()["id"]

    fetched = client.get(f"/incidents/{incident_id}")
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["suspects"], "background enrichment did not persist suspects"
    assert body["brief"] is not None
    assert [e["label"] for e in body["timeline"]] == [
        "detected",
        "correlate",
        "runbook",
        "impact",
        "brief",
        "briefed",
    ]


def test_resolve_acks_before_postmortem_generation(client, checkout_alert):
    created = _post(client, "/webhook/alert", checkout_alert.model_dump(mode="json")).json()

    resp = _post(client, "/webhook/resolve", {"incident_id": created["id"]})

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "resolved"
    assert body["postmortem"] is None


def test_resolve_background_task_persists_postmortem(client, checkout_alert):
    created = _post(client, "/webhook/alert", checkout_alert.model_dump(mode="json")).json()
    _post(client, "/webhook/resolve", {"incident_id": created["id"]})

    fetched = client.get(f"/incidents/{created['id']}")
    body = fetched.json()
    assert body["postmortem"] is not None
    assert "postmortem" in [e["label"] for e in body["timeline"]]


def test_resolve_unknown_incident_still_returns_404(client):
    resp = _post(client, "/webhook/resolve", {"incident_id": "inc-does-not-exist"})
    assert resp.status_code == 404
