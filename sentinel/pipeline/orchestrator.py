"""The orchestrator — runs the incident-response pipeline for an alert.

On an alert it executes stages 1–4 (correlate -> runbook -> impact -> brief),
recording each finding and a timeline entry on the incident. Each stage is
wrapped so one failing stage degrades gracefully rather than aborting the whole
response. On resolution it triggers postmortem generation (stage 5).
"""

from __future__ import annotations

from sentinel.adapters import Adapters, get_adapters
from sentinel.llm import LLMClient, get_llm
from sentinel.models import Alert, Incident
from sentinel.pipeline.brief import post_brief
from sentinel.pipeline.correlate import correlate
from sentinel.pipeline.impact import estimate_impact
from sentinel.pipeline.runbook import find_runbook
from sentinel.store import IncidentStore, get_store


class Orchestrator:
    """Coordinates adapters, pipeline stages, and the incident store."""

    def __init__(
        self,
        adapters: Adapters | None = None,
        store: IncidentStore | None = None,
        llm: LLMClient | None = None,
    ) -> None:
        self.adapters = adapters or get_adapters()
        self.store = store or get_store()
        self.llm = llm or get_llm()

    def handle_alert(self, alert: Alert) -> Incident:
        """Run the full response pipeline for an alert and persist the result."""
        incident = self.store.create_from_alert(alert)

        # Stage 1 — commit correlation
        with _stage(incident, "correlate", "Correlated recent commits/deploys"):
            incident.suspects = correlate(alert, self.adapters.github)
            if incident.top_suspect:
                s = incident.top_suspect
                incident.timeline[-1].detail = (
                    f"Top suspect {s.commit.short_sha} ({s.score:.0%}): {s.commit.message}"
                )

        # Stage 2 — runbook retrieval
        with _stage(incident, "runbook", "Searched runbooks"):
            incident.runbook_match = find_runbook(alert, self.adapters.runbooks)
            if incident.runbook_match:
                incident.timeline[-1].detail = (
                    f"Matched runbook: {incident.runbook_match.runbook.title}"
                )

        # Stage 3 — impact estimation
        with _stage(incident, "impact", "Estimated user impact"):
            incident.impact = estimate_impact(alert, self.adapters.metrics)
            incident.timeline[-1].detail = (
                f"{incident.impact.severity.value}: "
                f"~{incident.impact.affected_users:,} users affected"
            )

        # Stage 4 — brief + Slack post (adds its own 'briefed' timeline event)
        with _stage(incident, "brief", "Generated incident brief"):
            post_brief(incident, self.adapters.slack, self.llm)

        return self.store.save(incident)


class _stage:
    """Context manager: records a timeline event and isolates stage failures."""

    def __init__(self, incident: Incident, label: str, detail: str) -> None:
        self.incident = incident
        self.label = label
        self.detail = detail

    def __enter__(self) -> "_stage":
        self.incident.add_event(self.label, self.detail)
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is not None:
            self.incident.add_event(f"{self.label}:error", f"{exc_type.__name__}: {exc}")
            print(f"[orchestrator] stage '{self.label}' failed: {exc}")
            return True  # swallow: a degraded response beats no response
        return False


# Module-level convenience for callers that don't need to hold an instance.
def handle_alert(alert: Alert) -> Incident:
    return Orchestrator().handle_alert(alert)
