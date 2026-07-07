"""Tests for stage 4 — brief generation and Slack posting (offline/fallback)."""

from __future__ import annotations

from sentinel.adapters.slack_mock import MockSlackAdapter
from sentinel.llm import LLMClient
from sentinel.models import Incident
from sentinel.pipeline.brief import generate_brief, post_brief
from sentinel.pipeline.correlate import correlate
from sentinel.pipeline.impact import estimate_impact
from sentinel.pipeline.runbook import find_runbook


class _DisabledLLM(LLMClient):
    """Force the offline path regardless of environment."""

    @property
    def enabled(self) -> bool:
        return False


def _enriched_incident(alert, adapters) -> Incident:
    inc = Incident(id="inc-test", alert=alert)
    inc.suspects = correlate(alert, adapters.github)
    inc.runbook_match = find_runbook(alert, adapters.runbooks)
    inc.impact = estimate_impact(alert, adapters.metrics)
    return inc


def test_fallback_brief_contains_key_findings(checkout_alert, adapters):
    inc = _enriched_incident(checkout_alert, adapters)
    brief = generate_brief(inc, llm=_DisabledLLM())

    assert brief.generated_by == "fallback"
    assert "SEV2" in brief.headline
    # Mentions the culprit short sha and the runbook.
    assert inc.top_suspect.commit.short_sha in brief.body
    assert "checkout-5xx".split("-")[0] in brief.body.lower() or "runbook" in brief.body.lower()


def test_post_brief_records_on_incident_and_slack(checkout_alert, adapters):
    inc = _enriched_incident(checkout_alert, adapters)
    slack = MockSlackAdapter(echo=False)

    brief = post_brief(inc, slack, llm=_DisabledLLM(), channel="#test")

    assert len(slack.messages) == 1
    assert slack.messages[0].channel == "#test"
    assert inc.brief is brief
    assert inc.slack_ts is not None
    assert any(e.label == "briefed" for e in inc.timeline)


def test_llm_disabled_by_default_offline():
    # With no API key configured, the real client reports disabled.
    assert LLMClient().enabled is False
