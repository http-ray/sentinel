"""SQLite-backed incident store.

Incidents are stored as one JSON blob per row (Pydantic's own serialization),
not spread across a normalized schema -- the pipeline only needs whole-incident
create/get/save/list/resolve, and the shape of an Incident already changes as
new pipeline stages are added, so a schema-per-field would just be churn. The
public interface is unchanged from the in-memory version this replaces, so
callers (orchestrator, API layer, tests) don't need to change.

A single connection guarded by a lock keeps this simple; a real production
deployment would move to a connection pool or an async driver.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from sentinel.config import get_settings
from sentinel.models import Alert, Incident, IncidentStatus

_SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_incidents_created_at ON incidents(created_at);
"""


def _incident_id(alert: Alert) -> str:
    return f"inc-{alert.id}"


class IncidentStore:
    """Thread-safe SQLite incident store.

    Defaults to an in-memory database -- fresh and isolated per instance, same
    as the dict-backed store this replaces -- so existing callers that do
    ``IncidentStore()`` for test isolation keep working unchanged. Pass a real
    path (or use :func:`get_store`, which reads ``SENTINEL_DB_PATH``) for
    on-disk persistence.
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock, self._conn:
            self._conn.executescript(_SCHEMA)

    def create_from_alert(self, alert: Alert) -> Incident:
        """Create (or return existing) incident for an alert. Idempotent by alert id."""
        iid = _incident_id(alert)
        with self._lock:
            existing = self._get_locked(iid)
            if existing is not None:
                return existing
            incident = Incident(id=iid, alert=alert)
            incident.add_event("detected", f"Alert fired: {alert.title}")
            self._put_locked(incident)
            return incident

    def get(self, incident_id: str) -> Incident | None:
        with self._lock:
            return self._get_locked(incident_id)

    def save(self, incident: Incident) -> Incident:
        with self._lock:
            self._put_locked(incident)
            return incident

    def list(self) -> list[Incident]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT data FROM incidents ORDER BY created_at DESC"
            ).fetchall()
            return [Incident.model_validate_json(row[0]) for row in rows]

    def resolve(self, incident_id: str) -> Incident | None:
        with self._lock:
            incident = self._get_locked(incident_id)
            if incident is None:
                return None
            incident.status = IncidentStatus.RESOLVED
            incident.resolved_at = datetime.now(timezone.utc)
            incident.add_event("resolved", "Incident marked resolved.")
            self._put_locked(incident)
            return incident

    # -- internal; caller must hold self._lock ------------------------------ #

    def _get_locked(self, incident_id: str) -> Incident | None:
        row = self._conn.execute(
            "SELECT data FROM incidents WHERE id = ?", (incident_id,)
        ).fetchone()
        return Incident.model_validate_json(row[0]) if row else None

    def _put_locked(self, incident: Incident) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO incidents (id, created_at, data) VALUES (?, ?, ?)",
                (incident.id, incident.created_at.isoformat(), incident.model_dump_json()),
            )


_store: IncidentStore | None = None


def get_store() -> IncidentStore:
    """Return the process-wide incident store (singleton), backed by SENTINEL_DB_PATH."""
    global _store
    if _store is None:
        _store = IncidentStore(get_settings().db_path)
    return _store
