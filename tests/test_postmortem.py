"""Tests for stage 5 — postmortem generation and the resolve flow."""

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
    return Orchestrator(adapters=get_adapters(), store=IncidentStore(), llm=_DisabledLLM())


def test_resolve_generates_postmortem(checkout_alert):
    orch = _orch()
    incident = orch.handle_alert(checkout_alert)
    resolved = orch.resolve_incident(incident.id)

    assert resolved is not None
    assert resolved.status is IncidentStatus.RESOLVED
    assert resolved.resolved_at is not None
    assert resolved.postmortem is not None
    assert resolved.postmortem.generated_by == "fallback"


def test_postmortem_body_has_expected_sections(checkout_alert):
    orch = _orch()
    incident = orch.handle_alert(checkout_alert)
    pm = orch.resolve_incident(incident.id).postmortem

    for section in ("## Summary", "## Impact", "## Root Cause", "## Timeline", "## Action Items"):
        assert section in pm.body, f"missing section: {section}"
    # Grounded in the actual findings.
    assert "a1b2c3d4" in pm.body  # culprit commit
    assert "SEV2" in pm.body


def test_resolve_unknown_incident_returns_none():
    assert _orch().resolve_incident("inc-does-not-exist") is None


def test_timeline_includes_resolution_and_postmortem(checkout_alert):
    orch = _orch()
    incident = orch.handle_alert(checkout_alert)
    resolved = orch.resolve_incident(incident.id)
    labels = [e.label for e in resolved.timeline]
    assert "resolved" in labels
    assert "postmortem" in labels
    # postmortem should be the last event.
    assert labels[-1] == "postmortem"
