"""Embedding-based runbook retrieval (roadmap item 6).

An optional, more sophisticated alternative to the heuristic keyword scorer in
``runbook.py``: embeds the alert text and each runbook's text with a local
sentence-transformer model, then ranks by cosine similarity against a small
in-memory "vector store" -- just the list of runbook vectors, since the
corpus here is a handful of files, not something that needs FAISS/Chroma.

Off by default (``SENTINEL_USE_EMBEDDINGS=false``): the heuristic scorer is
deterministic, dependency-free, and already well-suited to a small, hand-
written runbook corpus. This exists to demonstrate a genuine local-ML
retrieval path, not because the heuristic is broken.

``sentence-transformers`` (and torch) are an optional dependency -- install
with ``pip install -e ".[embeddings]"``. Nothing in this module imports it at
module load time, so importing the pipeline never requires it; only actually
calling :func:`find_runbook_by_embedding` without an injected ``embed_fn``
does.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence

from sentinel.config import get_settings
from sentinel.models import Alert, Runbook, RunbookMatch

Vector = Sequence[float]
EmbedFn = Callable[[list[str]], list[Vector]]

_model = None  # lazily loaded sentence-transformers model, cached process-wide


def _runbook_text(runbook: Runbook) -> str:
    return f"{runbook.title}. {runbook.summary} Tags: {', '.join(runbook.tags)}."


def _alert_text(alert: Alert) -> str:
    parts = [alert.title, alert.summary, alert.service, *alert.labels.values()]
    return " ".join(p for p in parts if p)


def _default_embed_fn(texts: list[str]) -> list[Vector]:
    """Encode ``texts`` with a local sentence-transformers model (lazy-loaded)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer  # optional dependency

        _model = SentenceTransformer(get_settings().embedding_model)
    return _model.encode(texts, normalize_embeddings=True).tolist()


def _cosine_similarity(a: Vector, b: Vector) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def find_runbook_by_embedding(
    alert: Alert,
    runbooks: list[Runbook],
    *,
    embed_fn: EmbedFn | None = None,
) -> RunbookMatch | None:
    """Return the best-matching runbook by embedding cosine similarity, or None.

    ``embed_fn`` defaults to the real sentence-transformers model; tests inject
    a deterministic fake so the ranking logic is verified without ever loading
    a model. Unlike the heuristic scorer's exact-zero "no overlap" case,
    general sentence embeddings rarely land at exactly zero similarity for
    unrelated text, so this only rules out non-positive scores -- deliberately
    conservative rather than guessing an unvalidated similarity cutoff.
    """
    if not runbooks:
        return None

    embed = embed_fn or _default_embed_fn
    texts = [_alert_text(alert), *[_runbook_text(r) for r in runbooks]]
    vectors = embed(texts)
    alert_vec, runbook_vecs = vectors[0], vectors[1:]

    best_runbook: Runbook | None = None
    best_score = 0.0
    for runbook, vec in zip(runbooks, runbook_vecs):
        score = _cosine_similarity(alert_vec, vec)
        if score > best_score:
            best_score = score
            best_runbook = runbook

    if best_runbook is None:
        return None
    return RunbookMatch(runbook=best_runbook, score=round(best_score, 4))
