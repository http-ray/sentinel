"""FastAPI app exposing Sentinel's webhook ingestion and incident views.

Endpoints:
    POST /webhook/alert    Ingest a normalized alert -> creates/enriches an incident.
    POST /webhook/resolve  Mark an incident resolved -> triggers postmortem.
    GET  /incidents        List incidents (newest first).
    GET  /incidents/{id}   Fetch one incident.
    GET  /healthz          Liveness probe.

Any monitoring source maps its payload onto the normalized :class:`Alert` schema
before POSTing. Pipeline enrichment (commit correlation, runbook, impact, brief)
is wired in via the orchestrator; until then ingestion simply records incidents.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from sentinel.models import Alert, Incident
from sentinel.pipeline.orchestrator import Orchestrator
from sentinel.store import get_store

app = FastAPI(
    title="Sentinel",
    version="0.1.0",
    description="Autonomous AI incident-response agent.",
)


class ResolveRequest(BaseModel):
    incident_id: str


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook/alert", response_model=Incident, status_code=201)
def ingest_alert(alert: Alert) -> Incident:
    """Ingest an alert, run the response pipeline, and return the incident."""
    return Orchestrator().handle_alert(alert)


@app.post("/webhook/resolve", response_model=Incident)
def resolve_incident(req: ResolveRequest) -> Incident:
    incident = Orchestrator().resolve_incident(req.incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Unknown incident")
    return incident


@app.get("/incidents", response_model=list[Incident])
def list_incidents() -> list[Incident]:
    return get_store().list()


@app.get("/incidents/{incident_id}", response_model=Incident)
def get_incident(incident_id: str) -> Incident:
    incident = get_store().get(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Unknown incident")
    return incident
