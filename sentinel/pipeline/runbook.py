"""Stage 2 — runbook retrieval.

Score each runbook against the alert and return the best match. The mock uses
transparent keyword/tag/service scoring; the signature (alert + RunbookStore ->
RunbookMatch) is what matters, so an embedding-based store can replace the
scoring later without changing callers.
"""

from __future__ import annotations

import re

from sentinel.adapters.base import RunbookStore
from sentinel.config import get_settings
from sentinel.models import Alert, Runbook, RunbookMatch

# Scoring weights.
W_SERVICE = 3.0  # runbook explicitly lists the affected service
W_TAG = 2.0  # a runbook tag appears in the alert text
W_TERM = 0.5  # generic term overlap between alert text and runbook

_WORD = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def _alert_text(alert: Alert) -> str:
    parts = [alert.title, alert.summary, *alert.labels.values()]
    return " ".join(p for p in parts if p)


def score_runbook(alert: Alert, runbook: Runbook) -> float:
    """Transparent relevance score for one runbook against an alert."""
    alert_tokens = _tokens(_alert_text(alert))
    score = 0.0

    if alert.service in runbook.services:
        score += W_SERVICE

    for tag in runbook.tags:
        if tag.lower() in alert_tokens:
            score += W_TAG

    runbook_tokens = _tokens(f"{runbook.title} {runbook.summary}")
    overlap = alert_tokens & runbook_tokens
    # Drop very common short tokens to reduce noise.
    overlap = {t for t in overlap if len(t) > 3}
    score += W_TERM * len(overlap)

    return round(score, 4)


def find_runbook(alert: Alert, store: RunbookStore) -> RunbookMatch | None:
    """Return the best-matching runbook for ``alert``, or None if nothing scores.

    Uses heuristic keyword/tag/service scoring by default. Set
    ``SENTINEL_USE_EMBEDDINGS=true`` to use local sentence-transformer
    embeddings instead (see :mod:`sentinel.pipeline.embeddings`).
    """
    runbooks = store.all_runbooks()

    if get_settings().use_embeddings:
        from sentinel.pipeline.embeddings import find_runbook_by_embedding

        return find_runbook_by_embedding(alert, runbooks)

    best: RunbookMatch | None = None
    for runbook in runbooks:
        s = score_runbook(alert, runbook)
        if s <= 0:
            continue
        if best is None or s > best.score:
            best = RunbookMatch(runbook=runbook, score=s)
    return best
