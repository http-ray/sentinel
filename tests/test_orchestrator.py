"""End-to-end test for the orchestrator pipeline (offline)."""

from __future__ import annotations

from sentinel.adapters import get_adapters
from sentinel.llm import LLMClient
from sentinel.models import IncidentStatus
from sentinel.pipeline.orchestrator import Orchestrator
from sentinel.store.incidents import IncidentStore


class _DisabledLLM(LLMClient):
    @property
    def enabled(self) -> bool:
        return False


def _orch() -> Orchestrator:
    # Fresh adapters + store per test so state doesn't leak between tests.
    return Orchestrator(adapters=get_adapters(), store=IncidentStore(), llm=_DisabledLLM())


def test_alert_produces_fully_populated_incident(checkout_alert):
    orch = _orch()
    incident = orch.handle_alert(checkout_alert)

    # Every stage produced its finding.
    assert incident.suspects, "correlation produced no suspects"
    assert incident.runbook_match is not None, "no runbook matched"
    assert incident.impact is not None, "no impact estimate"
    assert incident.brief is not None, "no brief generated"
    assert incident.slack_ts is not None, "brief was not posted"

    # The findings are the expected ones for the sample scenario.
    assert incident.top_suspect.commit.short_sha == "a1b2c3d4"
    assert incident.runbook_match.runbook.id == "checkout-5xx"
    assert incident.impact.severity.value == "SEV2"
    assert incident.status is IncidentStatus.OPEN


def test_timeline_records_each_stage(checkout_alert):
    incident = _orch().handle_alert(checkout_alert)
    labels = [e.label for e in incident.timeline]
    for stage in ("detected", "correlate", "runbook", "impact", "brief", "briefed"):
        assert stage in labels, f"missing timeline stage: {stage}"


def test_incident_is_persisted_and_listable(checkout_alert):
    orch = _orch()
    incident = orch.handle_alert(checkout_alert)
    assert orch.store.get(incident.id) is incident
    assert incident in orch.store.list()


def test_pipeline_is_idempotent_on_repeated_alert(checkout_alert):
    orch = _orch()
    first = orch.handle_alert(checkout_alert)
    again = orch.handle_alert(checkout_alert)
    assert first.id == again.id
    assert len(orch.store.list()) == 1
