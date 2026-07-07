# Sentinel

**Autonomous AI incident-response agent.** The moment a production alert fires, Sentinel runs a
five-stage pipeline and hands your on-call engineer a complete picture — then writes the postmortem
once the incident is resolved.

1. **Identifies the likely bad commit** — correlates the alert against recent deploys/commits
2. **Finds the right runbook** — retrieves the matching remediation doc
3. **Estimates user impact** — quantifies blast radius and assigns a severity (SEV1–SEV4)
4. **Posts a Slack brief** — a concise, human-readable incident summary
5. **Auto-generates a postmortem** — a blameless Markdown report, on resolution

Sentinel runs **fully offline out of the box.** Every external system (GitHub, Slack, metrics) sits
behind an adapter interface with a mock implementation, so the whole pipeline executes with **zero API
keys**. Add an `ANTHROPIC_API_KEY` and the brief + postmortem become Claude-authored; swap in real
adapters and it drives live incidents — all without changing pipeline logic.

## How it works

```
Alert (webhook) ─▶ Orchestrator
                     ├─ 1. Correlate  → likely bad commit    (GitHubAdapter)
                     ├─ 2. Runbook    → best-match runbook    (RunbookStore)
                     ├─ 3. Impact     → blast-radius + SEV     (MetricsAdapter)
                     ├─ 4. Brief      → Claude → Slack         (LLM + SlackAdapter)
                     └─ 5. Postmortem → Claude report on resolve (LLM)
                     (incident state accumulated across stages in a store)
```

**Design principle — explainable first, LLM second.** Commit correlation, runbook retrieval, and
impact estimation are all *deterministic and testable*. Each suspect commit carries a 0–1 confidence
score and human-readable reasons, so an engineer can audit the "why", not trust a black box. The LLM
is used only to *write* the brief and postmortem from the structured findings the deterministic stages
produced.

## Quickstart

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows (macOS/Linux: source .venv/bin/activate)
pip install -e ".[dev]"
cp .env.example .env              # optional; defaults run fully offline
```

### Run the simulation (offline, no keys)

```bash
python scripts/simulate.py            # fire the sample checkout-service incident
python scripts/simulate.py --list     # list available sample alerts
python scripts/simulate.py --alert 1  # fire a different one
```

You'll see each stage: the ranked bad commit with confidence + reasons, the matched runbook, the
impact/severity, the Slack brief, and the generated postmortem.

### Run the server

```bash
uvicorn sentinel.api.main:app --reload
```

Then drive it over HTTP:

```bash
# Fire an alert (any monitoring source maps onto this normalized schema)
curl -s -X POST localhost:8000/webhook/alert \
  -H 'content-type: application/json' \
  -d '{
        "id": "alert-123",
        "title": "Elevated 5xx on checkout-service",
        "service": "checkout-service",
        "severity_hint": "SEV2",
        "summary": "5xx rate above 5% on /api/checkout/confirm",
        "fired_at": "2026-07-06T14:32:00Z",
        "source": "datadog"
      }'

# Inspect enriched incidents
curl -s localhost:8000/incidents

# Resolve it -> triggers postmortem generation
curl -s -X POST localhost:8000/webhook/resolve \
  -H 'content-type: application/json' \
  -d '{"incident_id": "inc-alert-123"}'
```

Interactive API docs are served at `http://localhost:8000/docs`.

### Endpoints

| Method | Path                | Purpose                                          |
| ------ | ------------------- | ------------------------------------------------ |
| POST   | `/webhook/alert`    | Ingest a normalized alert; runs the full pipeline |
| POST   | `/webhook/resolve`  | Mark an incident resolved; generates a postmortem |
| GET    | `/incidents`        | List incidents (newest first)                    |
| GET    | `/incidents/{id}`   | Fetch one incident                               |
| GET    | `/healthz`          | Liveness probe                                   |

## Configuration

All settings live in `.env` (see `.env.example`); defaults are offline-friendly.

| Variable              | Default           | Purpose                                                  |
| --------------------- | ----------------- | -------------------------------------------------------- |
| `SENTINEL_USE_MOCKS`  | `true`            | Use in-repo mock adapters (offline). `false` = real (TBD)|
| `ANTHROPIC_API_KEY`   | *(blank)*         | Set to enable Claude-authored brief + postmortem         |
| `SENTINEL_MODEL`      | `claude-sonnet-5` | Model for synthesis (override to `claude-opus-4-8`)      |
| `SLACK_CHANNEL`       | `#incidents`      | Target channel for the brief                             |

With no `ANTHROPIC_API_KEY`, the brief and postmortem use a deterministic template that produces an
equivalent document — the pipeline never depends on network access.

## Testing

```bash
pytest
```

Unit tests cover correlation ranking, runbook scoring, and impact/severity thresholds; an end-to-end
test asserts that an alert yields a fully populated incident with the expected findings.

## Project layout

```
sentinel/
  api/main.py            FastAPI app: webhooks + incident views
  pipeline/
    orchestrator.py      runs the 5 stages, records the timeline
    correlate.py         stage 1 — commit correlation (deterministic, scored)
    runbook.py           stage 2 — runbook retrieval
    impact.py            stage 3 — impact estimation + severity
    brief.py             stage 4 — brief synthesis + Slack post
    postmortem.py        stage 5 — postmortem generation
  adapters/              Protocol interfaces + mock implementations + factory
  llm/                   Anthropic client wrapper + prompt builders
  store/incidents.py     in-memory incident store
  models.py              shared Pydantic domain types
runbooks/                sample markdown runbooks
fixtures/                sample alerts, commits, deploys for the simulation
scripts/simulate.py      end-to-end offline demo
tests/                   pytest suite
```

## Extending Sentinel

Everything the pipeline touches is an adapter Protocol in `sentinel/adapters/base.py`. To go live,
implement the real versions behind those interfaces and set `SENTINEL_USE_MOCKS=false`:

- **GitHubAdapter** → GitHub commits/deploys API
- **MetricsAdapter** → Datadog / Prometheus / CloudWatch
- **RunbookStore** → embedding-based semantic search over your runbook corpus
- **SlackAdapter** → Slack Web API

Persistence (`store/incidents.py`) can likewise move from in-memory to SQLite/Postgres without
changing callers.

## Roadmap

- Real GitHub / Slack / Datadog adapters
- Embedding-based runbook retrieval
- Durable persistence (SQLite → Postgres)
- Webhook auth + a web dashboard
