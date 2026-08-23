"""Tests for embedding-based runbook retrieval.

All tests inject a fake, deterministic embed_fn -- none of them load
sentence-transformers or download a model, so this file stays fast and
network-free like the rest of the suite. Testing against a real model is a
manual, opt-in smoke test (see docs/engineering-log.md), not part of CI.
"""

from __future__ import annotations

from sentinel.config import Settings
from sentinel.models import Alert, Runbook
from sentinel.pipeline.embeddings import find_runbook_by_embedding
from sentinel.pipeline.runbook import find_runbook

_CHECKOUT = Runbook(id="checkout-5xx", title="Checkout 5xx", services=["checkout-service"])
_LATENCY = Runbook(id="service-latency", title="Service latency", services=["media-service"])
_DB = Runbook(id="database-incident", title="Database incident", services=["db"])


def _alert(service="checkout-service") -> Alert:
    return Alert(id="a1", title="Checkout errors spiking", service=service)


def _fake_embed_by_runbook_id() -> callable:
    """Hand-picked unit vectors: alert is closest to _CHECKOUT, then _LATENCY,
    orthogonal to _DB -- lets us assert an exact ranking without a real model."""
    vectors = {
        "__alert__": (1.0, 0.0, 0.0),
        "checkout-5xx": (0.9, 0.1, 0.0),  # near-parallel to the alert
        "service-latency": (0.5, 0.5, 0.0),  # partially related
        "database-incident": (0.0, 0.0, 1.0),  # orthogonal -- unrelated
    }

    def embed_fn(texts: list[str]) -> list[tuple[float, float, float]]:
        # First text is always the alert; the rest are runbook texts in order,
        # each starting with "<title>." -- match by the id embedded in fixtures above.
        out = [vectors["__alert__"]]
        for text in texts[1:]:
            for rb_id, title in (
                ("checkout-5xx", "Checkout 5xx"),
                ("service-latency", "Service latency"),
                ("database-incident", "Database incident"),
            ):
                if text.startswith(title):
                    out.append(vectors[rb_id])
                    break
        return out

    return embed_fn


def test_picks_the_highest_cosine_similarity_runbook():
    match = find_runbook_by_embedding(
        _alert(), [_DB, _LATENCY, _CHECKOUT], embed_fn=_fake_embed_by_runbook_id()
    )
    assert match is not None
    assert match.runbook.id == "checkout-5xx"
    # Cosine sim of (1,0,0) and (0.9,0.1,0) normalized.
    assert 0.9 < match.score <= 1.0


def test_ranks_partial_match_above_orthogonal_match():
    match = find_runbook_by_embedding(
        _alert(), [_DB, _LATENCY], embed_fn=_fake_embed_by_runbook_id()
    )
    assert match is not None
    assert match.runbook.id == "service-latency"


def test_orthogonal_only_returns_none():
    def embed_fn(texts: list[str]) -> list[tuple[float, float, float]]:
        return [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]  # alert, then one orthogonal runbook

    match = find_runbook_by_embedding(_alert(), [_DB], embed_fn=embed_fn)
    assert match is None


def test_empty_runbook_list_returns_none_without_calling_embed_fn():
    calls: list[list[str]] = []

    def embed_fn(texts: list[str]) -> list[tuple[float, float, float]]:
        calls.append(texts)
        return []

    assert find_runbook_by_embedding(_alert(), [], embed_fn=embed_fn) is None
    assert calls == []


def test_find_runbook_dispatches_to_embeddings_when_enabled(monkeypatch, adapters):
    monkeypatch.setattr(
        "sentinel.pipeline.runbook.get_settings",
        lambda: Settings(_env_file=None, SENTINEL_USE_EMBEDDINGS=True),
    )
    calls: list[object] = []

    def fake_find_runbook_by_embedding(alert, runbooks):
        calls.append(alert)
        return None

    monkeypatch.setattr(
        "sentinel.pipeline.embeddings.find_runbook_by_embedding",
        fake_find_runbook_by_embedding,
    )

    find_runbook(_alert(), adapters.runbooks)
    assert len(calls) == 1


def test_find_runbook_uses_heuristic_when_embeddings_disabled(monkeypatch, adapters, checkout_alert):
    monkeypatch.setattr(
        "sentinel.pipeline.runbook.get_settings",
        lambda: Settings(_env_file=None, SENTINEL_USE_EMBEDDINGS=False),
    )
    match = find_runbook(checkout_alert, adapters.runbooks)
    assert match is not None
    assert match.runbook.id == "checkout-5xx"
