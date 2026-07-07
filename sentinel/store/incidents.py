"""In-memory incident store.

Deliberately tiny and swappable: the whole pipeline only needs create / get /
update / list. A SQLite or Postgres implementation can replace this later without
changing callers.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone

from sentinel.models import Alert, Incident, IncidentStatus


def _incident_id(alert: Alert) -> str:
    return f"inc-{alert.id}"


class IncidentStore:
    """Thread-safe in-memory incident store."""

    def __init__(self) -> None:
        self._incidents: dict[str, Incident] = {}
        self._lock = threading.Lock()

    def create_from_alert(self, alert: Alert) -> Incident:
        """Create (or return existing) incident for an alert. Idempotent by alert id."""
        with self._lock:
            iid = _incident_id(alert)
            existing = self._incidents.get(iid)
            if existing is not None:
                return existing
            incident = Incident(id=iid, alert=alert)
            incident.add_event("detected", f"Alert fired: {alert.title}")
            self._incidents[iid] = incident
            return incident

    def get(self, incident_id: str) -> Incident | None:
        with self._lock:
            return self._incidents.get(incident_id)

    def save(self, incident: Incident) -> Incident:
        with self._lock:
            self._incidents[incident.id] = incident
            return incident

    def list(self) -> list[Incident]:
        with self._lock:
            return sorted(
                self._incidents.values(), key=lambda i: i.created_at, reverse=True
            )

    def resolve(self, incident_id: str) -> Incident | None:
        with self._lock:
            incident = self._incidents.get(incident_id)
            if incident is None:
                return None
            incident.status = IncidentStatus.RESOLVED
            incident.resolved_at = datetime.now(timezone.utc)
            incident.add_event("resolved", "Incident marked resolved.")
            return incident


_store: IncidentStore | None = None


def get_store() -> IncidentStore:
    """Return the process-wide incident store (singleton)."""
    global _store
    if _store is None:
        _store = IncidentStore()
    return _store
