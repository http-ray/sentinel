"""Tests for the SQLite-backed IncidentStore."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sentinel.models import Alert, Incident, IncidentStatus
from sentinel.store.incidents import IncidentStore


def _alert(alert_id="a1", service="checkout-service") -> Alert:
    return Alert(id=alert_id, title="t", service=service)


def test_default_store_is_isolated_in_memory():
    # No path given -> fresh, empty, per-instance store, same as the old dict version.
    a, b = IncidentStore(), IncidentStore()
    a.create_from_alert(_alert())
    assert len(a.list()) == 1
    assert len(b.list()) == 0


def test_create_from_alert_is_idempotent():
    store = IncidentStore()
    first = store.create_from_alert(_alert())
    second = store.create_from_alert(_alert())
    assert first.id == second.id
    assert len(store.list()) == 1


def test_get_returns_none_for_unknown_id():
    store = IncidentStore()
    assert store.get("inc-does-not-exist") is None


def test_save_persists_mutations():
    store = IncidentStore()
    incident = store.create_from_alert(_alert())
    incident.status = IncidentStatus.RESOLVED
    store.save(incident)

    fetched = store.get(incident.id)
    assert fetched is not None
    assert fetched.status is IncidentStatus.RESOLVED


def test_resolve_marks_status_and_records_timeline():
    store = IncidentStore()
    incident = store.create_from_alert(_alert())
    resolved = store.resolve(incident.id)

    assert resolved is not None
    assert resolved.status is IncidentStatus.RESOLVED
    assert resolved.resolved_at is not None
    assert any(e.label == "resolved" for e in resolved.timeline)

    # The mutation was actually persisted, not just returned.
    assert store.get(incident.id).status is IncidentStatus.RESOLVED


def test_resolve_unknown_id_returns_none():
    assert IncidentStore().resolve("inc-does-not-exist") is None


def test_list_orders_newest_first():
    store = IncidentStore()
    older = Incident(id="inc-older", alert=_alert("older"))
    older.created_at = datetime.now(timezone.utc) - timedelta(hours=1)
    newer = Incident(id="inc-newer", alert=_alert("newer"))

    store.save(older)
    store.save(newer)

    ids = [i.id for i in store.list()]
    assert ids == ["inc-newer", "inc-older"]


def test_persistence_survives_across_instances_on_disk(tmp_path):
    db_path = tmp_path / "sentinel-test.db"

    store1 = IncidentStore(db_path)
    incident = store1.create_from_alert(_alert())

    # A fresh IncidentStore pointed at the same file sees the same data.
    store2 = IncidentStore(db_path)
    fetched = store2.get(incident.id)
    assert fetched is not None
    assert fetched == incident
