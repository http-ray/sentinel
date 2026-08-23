"""FastAPI app exposing Sentinel's webhook ingestion and incident views.

Endpoints:
    POST /webhook/alert    ACK an alert immediately -> stages 1-4 run in the background.
    POST /webhook/resolve  ACK a resolve request immediately -> postmortem (stage 5)
                            runs in the background.
    GET  /incidents        List incidents (newest first).
    GET  /incidents/{id}   Fetch one incident.
    GET  /healthz          Liveness probe.

Any monitoring source maps its payload onto the normalized :class:`Alert` schema
before POSTing. Both POST endpoints return a 202 with the incident as it exists
at the moment of acknowledgement (not yet enriched) -- poll GET /incidents/{id}
to see suspects/runbook/impact/brief (or the postmortem) land as the background
task completes. This is what makes ingestion non-blocking: the caller isn't
held open for however long commit correlation, an LLM call, and a Slack post
take.

Both POST endpoints require a valid HMAC-SHA256 signature once
``SENTINEL_WEBHOOK_SECRET`` is set (see ``sentinel.api.auth``); unset, they're
open, matching every other real-integration credential's offline-friendly default.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from pydantic import BaseModel

from sentinel.api.auth import verify_webhook_signature
from sentinel.models import Alert, Incident
from sentinel.pipeline.orchestrator import Orchestrator
from sentinel.store import IncidentStore, get_store

app = FastAPI(
    title="Sentinel",
    version="0.1.0",
    description="Autonomous AI incident-response agent.",
)


class ResolveRequest(BaseModel):
    incident_id: str


def get_orchestrator() -> Orchestrator:
    return Orchestrator()


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/webhook/alert",
    response_model=Incident,
    status_code=202,
    dependencies=[Depends(verify_webhook_signature)],
)
def ingest_alert(
    alert: Alert,
    background_tasks: BackgroundTasks,
    orch: Annotated[Orchestrator, Depends(get_orchestrator)],
) -> Incident:
    """Record the alert and immediately return; the pipeline runs in the background."""
    incident = orch.create_incident(alert)
    background_tasks.add_task(orch.enrich_incident, incident)
    return incident


@app.post(
    "/webhook/resolve",
    response_model=Incident,
    status_code=202,
    dependencies=[Depends(verify_webhook_signature)],
)
def resolve_incident(
    req: ResolveRequest,
    background_tasks: BackgroundTasks,
    orch: Annotated[Orchestrator, Depends(get_orchestrator)],
) -> Incident:
    """Mark the incident resolved and immediately return; postmortem generation
    (stage 5) runs in the background."""
    incident = orch.mark_resolved(req.incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Unknown incident")
    background_tasks.add_task(orch.generate_and_save_postmortem, incident)
    return incident


@app.get("/incidents", response_model=list[Incident])
def list_incidents(store: Annotated[IncidentStore, Depends(get_store)]) -> list[Incident]:
    return store.list()


@app.get("/incidents/{incident_id}", response_model=Incident)
def get_incident(
    incident_id: str, store: Annotated[IncidentStore, Depends(get_store)]
) -> Incident:
    incident = store.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Unknown incident")
    return incident
