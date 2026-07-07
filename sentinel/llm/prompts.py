"""Prompt builders for the LLM-authored artifacts (brief, postmortem).

These build a compact, structured summary of everything the deterministic stages
found, and ask the model only to *write* — not to re-derive facts. That keeps the
analysis auditable and the LLM's job narrow.
"""

from __future__ import annotations

from sentinel.models import Incident

BRIEF_SYSTEM = (
    "You are Sentinel, an autonomous incident-response agent. You write concise, "
    "calm, factual incident briefs for an on-call engineering channel. Never "
    "invent facts beyond the structured findings provided. Prefer bullet points. "
    "Keep it under ~150 words."
)

POSTMORTEM_SYSTEM = (
    "You are Sentinel, an autonomous incident-response agent. You write blameless "
    "postmortems in Markdown, grounded only in the structured findings provided. "
    "Use these sections: Summary, Impact, Root Cause, Timeline, Action Items. Be "
    "specific and blameless; do not invent facts."
)


def _findings_block(incident: Incident) -> str:
    a = incident.alert
    lines = [
        f"Incident ID: {incident.id}",
        f"Alert: {a.title} (service={a.service}, source={a.source})",
        f"Fired at: {a.fired_at.isoformat()}",
        f"Summary: {a.summary or '(none)'}",
    ]

    if incident.impact:
        i = incident.impact
        lines += [
            "",
            "Impact estimate:",
            f"  Severity: {i.severity.value}",
            f"  Error rate: {i.error_rate:.1%} (baseline {i.baseline_error_rate:.1%})",
            f"  Affected users: ~{i.affected_users:,}",
            f"  Throughput: {i.requests_per_min:,.0f} req/min",
        ]

    if incident.top_suspect:
        s = incident.top_suspect
        lines += [
            "",
            "Most likely bad commit:",
            f"  {s.commit.short_sha} — {s.commit.message} (by {s.commit.author})",
            f"  Confidence: {s.score:.2f}",
            f"  Reasons: {'; '.join(s.reasons) or '(none)'}",
        ]
        if s.deploy:
            lines.append(f"  Shipped by deploy {s.deploy.id} at {s.deploy.deployed_at.isoformat()}")

    if incident.runbook_match:
        r = incident.runbook_match.runbook
        lines += ["", f"Matched runbook: {r.title} (id={r.id})", f"  Summary: {r.summary}"]

    if incident.timeline:
        lines += ["", "Timeline:"]
        for e in incident.timeline:
            lines.append(f"  {e.at.isoformat()} — {e.label}: {e.detail}")

    if incident.resolved_at:
        lines.append(f"\nResolved at: {incident.resolved_at.isoformat()}")

    return "\n".join(lines)


def build_brief_prompt(incident: Incident) -> str:
    return (
        "Write a Slack incident brief from these findings. Lead with severity and "
        "a one-line headline, then the likely cause, impact, and the recommended "
        "first action from the runbook.\n\n"
        f"{_findings_block(incident)}"
    )


def build_postmortem_prompt(incident: Incident) -> str:
    return (
        "Write a blameless postmortem in Markdown from these findings.\n\n"
        f"{_findings_block(incident)}"
    )
