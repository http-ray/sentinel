"""Fire a fixture alert through the full Sentinel pipeline and print each stage.

Runs entirely offline (mock adapters + templated LLM fallback) unless an
ANTHROPIC_API_KEY is configured, in which case the brief and postmortem are
Claude-authored.

Usage:
    python scripts/simulate.py                 # first sample alert
    python scripts/simulate.py --alert 1       # choose alert by index
    python scripts/simulate.py --list          # list available sample alerts
"""

from __future__ import annotations

import argparse
import io
import json
import sys

from sentinel.adapters import get_adapters
from sentinel.config import get_settings
from sentinel.llm import get_llm
from sentinel.models import Alert
from sentinel.pipeline.orchestrator import Orchestrator
from sentinel.store.incidents import IncidentStore

RULE = "=" * 72


def _force_utf8_stdout() -> None:
    """Make stdout UTF-8 so Slack-style glyphs render on any console."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            return
        except Exception:
            pass
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def _load_alerts() -> list[Alert]:
    path = get_settings().fixtures_dir / "sample_alerts.json"
    return [Alert(**a) for a in json.loads(path.read_text("utf-8"))]


def _section(title: str) -> None:
    print(f"\n{RULE}\n{title}\n{RULE}")


def run(alert: Alert) -> None:
    settings = get_settings()
    mode = "Claude-authored" if settings.llm_enabled else "offline template"
    print(RULE)
    print(f" SENTINEL — autonomous incident response  ({mode}, model={settings.model})")
    print(RULE)
    print(f"\n:rotating_light: ALERT: {alert.title}")
    print(f"   service={alert.service}  severity_hint={alert.severity_hint}  source={alert.source}")
    print(f"   {alert.summary}")

    adapters = get_adapters()
    # We render the brief ourselves in Stage 4; silence the mock's raw echo.
    if hasattr(adapters.slack, "echo"):
        adapters.slack.echo = False
    orch = Orchestrator(adapters=adapters, store=IncidentStore(), llm=get_llm())
    incident = orch.handle_alert(alert)

    _section("STAGE 1 — LIKELY BAD COMMIT")
    if incident.top_suspect:
        s = incident.top_suspect
        print(f"{s.commit.short_sha}  {s.commit.message}")
        print(f"   author={s.commit.author}  confidence={s.score:.0%}")
        if s.deploy:
            print(f"   deploy={s.deploy.id} -> {s.deploy.environment} @ {s.deploy.deployed_at.isoformat()}")
        for r in s.reasons:
            print(f"   - {r}")
        others = incident.suspects[1:4]
        if others:
            print("   other candidates:")
            for o in others:
                print(f"     {o.commit.short_sha} {o.score:.0%}  {o.commit.message}")
    else:
        print("   (no suspect identified)")

    _section("STAGE 2 — RUNBOOK")
    if incident.runbook_match:
        rb = incident.runbook_match.runbook
        print(f"{rb.title}  (id={rb.id}, score={incident.runbook_match.score})")
        print(f"   {rb.summary}")
    else:
        print("   (no runbook matched)")

    _section("STAGE 3 — USER IMPACT")
    if incident.impact:
        for note in incident.impact.notes:
            print(f"   {note}")
        print(f"   => SEVERITY: {incident.impact.severity.value}")
    else:
        print("   (impact not estimated)")

    _section("STAGE 4 — SLACK BRIEF")
    if incident.brief:
        print(f"[generated_by={incident.brief.generated_by}]\n")
        print(incident.brief.body)

    _section("STAGE 5 — POSTMORTEM (after resolution)")
    resolved = orch.resolve_incident(incident.id)
    if resolved and resolved.postmortem:
        print(f"[generated_by={resolved.postmortem.generated_by}]\n")
        print(resolved.postmortem.body)

    _section("DONE")
    print(f"Incident {incident.id} — final status: {resolved.status.value}")
    print(f"Timeline: {' -> '.join(e.label for e in resolved.timeline)}")


def main() -> None:
    _force_utf8_stdout()
    parser = argparse.ArgumentParser(description="Simulate a Sentinel incident response.")
    parser.add_argument("--alert", type=int, default=0, help="Index of the sample alert to fire.")
    parser.add_argument("--list", action="store_true", help="List available sample alerts.")
    args = parser.parse_args()

    alerts = _load_alerts()
    if args.list:
        for i, a in enumerate(alerts):
            print(f"[{i}] {a.service}: {a.title}")
        return

    if not 0 <= args.alert < len(alerts):
        parser.error(f"--alert must be 0..{len(alerts) - 1}")
    run(alerts[args.alert])


if __name__ == "__main__":
    main()
