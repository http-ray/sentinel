# Sentinel Roadmap

This file is the working plan for Sentinel's next phase — turning it from a well-architected mock-first pipeline into a system with real integrations. Claude Code should read this file at the start of any session and update it (check items off, add notes) as work completes. Don't start work outside the current active item without checking in first.

**Status legend:** ⬜ not started · 🔶 in progress · ✅ done

---

## Current priority order

### 1. ✅ Real GitHub adapter
- [x] `GitHubAdapter` implementing the existing `adapters/base.py` Protocol interface
- [x] Read-only PAT auth via env var (same pattern as `ANTHROPIC_API_KEY`)
- [x] Wired into the existing factory — `SENTINEL_USE_MOCKS` still toggles cleanly
- [x] Tests added, consistent with existing suite style
- [x] Log this in `docs/engineering-log.md` when done

### 2. ✅ GitHub Actions CI
- [x] `.github/workflows/ci.yml` — lint + pytest on push/PR
- [x] Confirm it actually runs green on the current test suite before considering this done

### 3. ⬜ Webhook authentication
- [ ] Shared-secret or HMAC signature verification on `/webhook/alert`
- [ ] Natural follow-on once the GitHub adapter is real — do this alongside a real GitHub webhook, not the PAT-only version

### 4. ⬜ SQLite persistence
- [ ] Replace in-memory store in `store/incidents.py`
- [ ] Should be low-effort given it's already isolated behind its own module

### 5. ⬜ Async pipeline execution
- [ ] ACK webhook immediately, process the 5-stage pipeline in the background (asyncio background tasks)
- [ ] This is what makes "real-time system" an honest claim, not aspirational

### 6. ⬜ Embedding-based runbook retrieval
- [ ] Replace heuristic runbook matching with a small local vector store (e.g. sentence-transformers + cosine similarity)
- [ ] This is the genuinely "AI engineering" item on this list, not just "called an API"

### 7. ⬜ Real Docker support
- [ ] Dockerfile + docker-compose for the FastAPI server
- [ ] Makes "Docker" on the resume true again

### 8. ⬜ (Optional) Discord webhook instead of real Slack
- [ ] Slack app approval/workspace setup is disproportionate friction for the signal it adds
- [ ] A Discord webhook is functionally equivalent for demo purposes — do this only if you want the "posts somewhere real" checkbox

---

## Explicitly out of scope for now
- Kubernetes / production-grade deploy infra — not needed for a portfolio-stage project
- Real Datadog/metrics adapter — lower priority than GitHub; revisit after items 1–7
- Multi-tenant or auth/user system — not the point of this project

---

## Notes for Claude Code
- Follow the existing Protocol/adapter/factory pattern for any new integration — don't introduce a different structure per adapter.
- Commit in small, logical chunks (interface → implementation → tests → wiring), not one large diff per item.
- Run the existing pytest suite before and after any pipeline change.
- When an item is completed, mark it ✅ above **and** add a dated entry to `docs/engineering-log.md` describing what changed and why.
