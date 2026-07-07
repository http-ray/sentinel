"""Stage 1 — commit correlation.

Given an alert, rank recent commits by how likely each is the root cause. This is
deliberately *deterministic and explainable* (not an LLM guess): every suspect
carries a 0–1 score and human-readable reasons, so an on-call engineer can judge
the reasoning rather than trust a black box.

Signals, combined into the score:
  * time proximity   — commits/deploys shortly before the alert are likelier
  * deploy linkage   — a commit that was actually deployed (esp. right before the
                       alert) is far likelier than one that only merged
  * service overlap  — commit touches the alert's affected service
  * risk size        — large diffs are riskier than trivial ones
"""

from __future__ import annotations

from datetime import timedelta

from sentinel.adapters.base import GitHubAdapter
from sentinel.models import Alert, Commit, CommitSuspect, Deploy

# Lookback window for candidate commits/deploys before the alert.
LOOKBACK = timedelta(hours=6)

# A deploy within this window before the alert is treated as a prime suspect.
DEPLOY_HOT_WINDOW = timedelta(minutes=30)

# Scoring weights (kept explicit so the ranking is auditable).
W_TIME = 0.35
W_DEPLOY = 0.35
W_SERVICE = 0.20
W_RISK = 0.10


def _time_proximity_score(minutes_before: float) -> float:
    """1.0 at the moment of the alert, decaying to 0 across the lookback window."""
    span = LOOKBACK.total_seconds() / 60.0
    if minutes_before < 0:  # after the alert — not a cause
        return 0.0
    return max(0.0, 1.0 - (minutes_before / span))


def _risk_score(commit: Commit) -> float:
    """Larger diffs are riskier. Saturates so one huge commit doesn't dominate."""
    churn = commit.additions + commit.deletions
    if churn <= 0:
        return 0.0
    return min(1.0, churn / 300.0)


def correlate(alert: Alert, github: GitHubAdapter) -> list[CommitSuspect]:
    """Return commit suspects for ``alert``, highest score first."""
    cutoff = alert.fired_at
    window_start = cutoff - LOOKBACK

    commits = [
        c
        for c in github.recent_commits(alert.service, cutoff)
        if c.timestamp >= window_start
    ]
    deploys = [
        d
        for d in github.recent_deploys(alert.service, cutoff)
        if d.deployed_at >= window_start
    ]

    # Map commit sha -> the most recent deploy that shipped it (if any).
    deploy_by_sha: dict[str, Deploy] = {}
    for d in sorted(deploys, key=lambda d: d.deployed_at):
        deploy_by_sha[d.commit_sha] = d

    suspects: list[CommitSuspect] = []
    for commit in commits:
        reasons: list[str] = []
        deploy = deploy_by_sha.get(commit.sha)

        # Time proximity — measured from deploy if deployed, else commit time.
        event_time = deploy.deployed_at if deploy else commit.timestamp
        minutes_before = (cutoff - event_time).total_seconds() / 60.0
        time_score = _time_proximity_score(minutes_before)
        if minutes_before >= 0:
            reasons.append(
                f"{'Deployed' if deploy else 'Committed'} {minutes_before:.0f} min "
                f"before the alert"
            )

        # Deploy linkage.
        deploy_score = 0.0
        if deploy is not None:
            deploy_score = 0.6
            if cutoff - deploy.deployed_at <= DEPLOY_HOT_WINDOW:
                deploy_score = 1.0
                reasons.append(
                    f"Deploy {deploy.id} shipped this commit to "
                    f"{deploy.environment} just before the alert"
                )
            else:
                reasons.append(f"Shipped via deploy {deploy.id}")

        # Service overlap.
        service_score = 0.0
        if alert.service in commit.services_touched:
            service_score = 1.0
            reasons.append(f"Touches the affected service ({alert.service})")

        # Risk size.
        risk_score = _risk_score(commit)
        if risk_score >= 0.5:
            reasons.append(
                f"Large change (+{commit.additions}/-{commit.deletions})"
            )

        score = (
            W_TIME * time_score
            + W_DEPLOY * deploy_score
            + W_SERVICE * service_score
            + W_RISK * risk_score
        )

        suspects.append(
            CommitSuspect(
                commit=commit,
                deploy=deploy,
                score=round(score, 4),
                reasons=reasons,
            )
        )

    suspects.sort(key=lambda s: s.score, reverse=True)
    return suspects
