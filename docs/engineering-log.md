# Engineering Log

A running record of real changes to Sentinel — what was built, why, and any trade-offs made along the way. This isn't a changelog of every commit; it's for the changes worth being able to explain in an interview. Each entry should be short enough to write in five minutes, right after the work, while the reasoning is still fresh.

Template for each entry:

```
## YYYY-MM-DD — Short title

**What changed:** One or two sentences.

**Why:** The actual reasoning — what problem this solves, what it was before.

**Trade-offs / what I'd do differently at scale:** Optional but valuable — shows judgment, not just output.
```

---

## 2026-08-23 — Real GitHub adapter

**What changed:** Added `RealGitHubAdapter`, a GitHub REST API-backed implementation of the existing `GitHubAdapter` Protocol, authenticated with a read-only PAT (`GITHUB_TOKEN`/`GITHUB_REPO`, same opt-in pattern as `ANTHROPIC_API_KEY`). Wired it into `adapters/factory.py` so `SENTINEL_USE_MOCKS=false` now actually does something for GitHub instead of unconditionally raising `NotImplementedError` — it builds the real adapter if credentials are present, or raises a specific error naming exactly which env vars are missing if not. Metrics, runbooks, and Slack still have no real adapter, so they stay mocked in both modes; that's a deliberate, honest gap, not an oversight. Added 10 new offline tests (`httpx.MockTransport`, no real network calls) covering commit/deploy parsing, service tagging, 404/error handling, and the factory's branching logic. Full suite: 28 → 38 passing, no regressions.

**Why:** This was the top item on the roadmap and the prerequisite for making "root-cause commit identification" an honest claim rather than one running entirely against fixture JSON. It's also the one piece the rest of the correlation pipeline (`pipeline/correlate.py`) actually depends on for real signal — the scoring logic was already real, it just had nothing but mock data to score.

**Trade-offs / what I'd do differently at scale:** The adapter fetches full commit detail (`/commits/{sha}`) for every summary returned by the list endpoint to get accurate `additions`/`deletions`/`files_changed` — that's an N+1 call pattern against a rate-limited API. Fine at `limit=25` for a portfolio-scale demo; at real scale I'd either cache commit details or only fetch the detail for the top-N candidates after an initial cheap scoring pass on the summary data. I also collapsed "service" to a 1:1 mapping with the configured repo (every commit/deploy from `GITHUB_REPO` is tagged with the repo's short name) rather than inferring per-file service ownership — that matches how this adapter is actually scoped (one repo = one service) but wouldn't hold up against a monorepo without a real service-ownership mapping.
