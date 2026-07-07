"""Core domain models for Sentinel.

These Pydantic models are the shared vocabulary across the whole pipeline. Every
adapter and stage speaks in terms of these types, which is what lets us swap mock
integrations for real ones without touching pipeline logic.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Severity(str, Enum):
    """Incident severity, worst (SEV1) to lowest (SEV4)."""

    SEV1 = "SEV1"  # critical: broad outage / revenue-impacting
    SEV2 = "SEV2"  # major: significant degradation
    SEV3 = "SEV3"  # minor: limited impact
    SEV4 = "SEV4"  # negligible: informational


class IncidentStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #


class Alert(BaseModel):
    """A normalized alert. Any monitoring source maps onto this schema."""

    id: str = Field(..., description="Stable alert identifier from the source.")
    title: str
    service: str = Field(..., description="Affected service, e.g. 'checkout-service'.")
    severity_hint: Optional[Severity] = Field(
        default=None, description="Optional severity supplied by the source."
    )
    summary: str = Field(default="", description="Human-readable alert description.")
    labels: dict[str, str] = Field(
        default_factory=dict, description="Arbitrary source labels/tags."
    )
    fired_at: datetime = Field(default_factory=_now)
    source: str = Field(default="webhook", description="Originating system.")


class Commit(BaseModel):
    """A source commit, optionally associated with a deploy."""

    sha: str
    message: str
    author: str
    timestamp: datetime
    files_changed: list[str] = Field(default_factory=list)
    services_touched: list[str] = Field(
        default_factory=list, description="Services this commit is known to affect."
    )
    additions: int = 0
    deletions: int = 0

    @property
    def short_sha(self) -> str:
        return self.sha[:8]


class Deploy(BaseModel):
    """A deployment event that shipped a commit to an environment."""

    id: str
    commit_sha: str
    service: str
    environment: str = "production"
    deployed_at: datetime
    deployed_by: str = ""


# --------------------------------------------------------------------------- #
# Pipeline outputs
# --------------------------------------------------------------------------- #


class CommitSuspect(BaseModel):
    """A commit ranked as a possible root cause, with an explainable score."""

    commit: Commit
    deploy: Optional[Deploy] = None
    score: float = Field(..., description="Confidence 0.0–1.0.")
    reasons: list[str] = Field(
        default_factory=list, description="Human-readable why-this-commit signals."
    )


class Runbook(BaseModel):
    """A remediation document."""

    id: str
    title: str
    services: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    summary: str = ""
    body: str = ""
    path: Optional[str] = None


class RunbookMatch(BaseModel):
    runbook: Runbook
    score: float


class ImpactEstimate(BaseModel):
    """Blast-radius estimate for an alert window."""

    service: str
    error_rate: float = Field(..., description="Fraction of requests failing, 0.0–1.0.")
    requests_per_min: float
    affected_users: int
    baseline_error_rate: float = 0.0
    severity: Severity
    notes: list[str] = Field(default_factory=list)


class IncidentBrief(BaseModel):
    """The synthesized brief posted to Slack."""

    headline: str
    body: str
    generated_by: str = Field(
        default="fallback", description="'llm' or 'fallback'."
    )


class Postmortem(BaseModel):
    """The post-resolution report."""

    title: str
    body: str
    generated_by: str = "fallback"


class TimelineEvent(BaseModel):
    at: datetime = Field(default_factory=_now)
    label: str
    detail: str = ""


# --------------------------------------------------------------------------- #
# Aggregate
# --------------------------------------------------------------------------- #


class Incident(BaseModel):
    """The evolving state of one incident, accumulated across pipeline stages."""

    id: str
    alert: Alert
    status: IncidentStatus = IncidentStatus.OPEN
    created_at: datetime = Field(default_factory=_now)
    resolved_at: Optional[datetime] = None

    suspects: list[CommitSuspect] = Field(default_factory=list)
    runbook_match: Optional[RunbookMatch] = None
    impact: Optional[ImpactEstimate] = None
    brief: Optional[IncidentBrief] = None
    postmortem: Optional[Postmortem] = None

    timeline: list[TimelineEvent] = Field(default_factory=list)
    slack_ts: Optional[str] = Field(
        default=None, description="Timestamp/id of the posted Slack message."
    )

    def add_event(self, label: str, detail: str = "") -> None:
        self.timeline.append(TimelineEvent(label=label, detail=detail))

    @property
    def top_suspect(self) -> Optional[CommitSuspect]:
        return self.suspects[0] if self.suspects else None
