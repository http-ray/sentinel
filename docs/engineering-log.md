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

---

## 2026-08-23 — GitHub Actions CI

**What changed:** Added `.github/workflows/ci.yml`: runs `ruff check .` and `pytest -q` on every push to `main` and every PR, Python 3.12, installed via `pip install -e ".[dev]"`. Pinned ruff to a conservative rule set (`F`, `E4`, `E7`, `E9` — pyflakes plus real pycodestyle errors, not line-length/formatting opinions the codebase never adopted) rather than accepting its much broader modern defaults, which would have flagged ~20 pre-existing style choices unrelated to correctness. Fixed the two real issues that selection did surface (a dead variable in the metrics mock, an unused import in a test). Verified green on GitHub after push, not just locally.

**Why:** Roadmap item 2, and a prerequisite for trusting any future PR without manually re-running the suite. Setting up lint also surfaced a real latent bug: several tests called `get_settings()`/`get_adapters()` with no override, so a developer's local `.env` (in this case, `SENTINEL_USE_MOCKS=false` left over from the GitHub adapter smoke test) silently changed what the suite exercised — 5 tests failed hitting the live API instead of mocks. Fixed by having every test fixture build `Settings(_env_file=None)` explicitly, so the suite is hermetic regardless of local `.env` contents. This would have made CI itself unreliable in a subtler way (CI has no `.env`, so it wouldn't have hit this specific failure — but the underlying fragility, tests silently depending on ambient state instead of being self-contained, was a real correctness gap worth closing while I had it in front of me).

**Trade-offs / what I'd do differently at scale:** No dependency caching between runs (`actions/setup-python`'s pip cache isn't enabled) and no matrix across Python versions — both fine for a single-maintainer portfolio project with a small dependency set and a `requires-python >=3.10` floor that isn't being actively tested. I chose a narrow, explicit lint rule set over ruff's fuller defaults specifically to avoid a large drive-by reformatting diff in a CI-setup commit; the trade-off is that real modernization opportunities (e.g. `Optional[X]` → `X | None`) stay unflagged until someone deliberately opts into them.

---

## 2026-08-23 — Webhook authentication

**What changed:** Added `sentinel/api/auth.py`: a FastAPI dependency that requires a valid `X-Sentinel-Signature-256` header (HMAC-SHA256 over the raw request body, the same scheme GitHub itself uses for its webhooks) once `SENTINEL_WEBHOOK_SECRET` is set. Blank secret (the default) disables verification entirely, matching every other real-integration credential's offline-friendly default in this project. Wired it onto both `/webhook/alert` and `/webhook/resolve` as a route dependency. Added 8 tests: full coverage of the auth dependency against an isolated dummy app (disabled-by-default, missing header, wrong signature, signature computed with the wrong secret, tampered body, valid signature), plus two integration checks confirming it's actually wired onto the real endpoints. Full suite: 38 → 46 passing, no regressions.

**Why:** Roadmap item 3. `/webhook/alert` is a public-facing ingestion endpoint that triggers a real pipeline run (LLM calls, Slack posts, GitHub API calls once real credentials are configured) — right now anyone who finds the URL can POST arbitrary alerts and make Sentinel act on them. HMAC-over-the-body is the standard shape for this problem (GitHub, Stripe, and most webhook providers all use some variant), so implementing it this way means the same mental model transfers if a real upstream (GitHub webhooks, PagerDuty, etc.) is added as a source later.

I also corrected the roadmap's own note on this item, which said to do this "alongside a real GitHub webhook, not the PAT-only version." That doesn't describe anything on this roadmap — `/webhook/alert` is Sentinel's own alert intake, not a GitHub webhook receiver, and item 1 deliberately chose PAT-polling. Left a note in `docs/ROADMAP.md` explaining the correction so it doesn't cause confusion again.

**Trade-offs / what I'd do differently at scale:** Hit one real FastAPI dependency-injection gotcha worth remembering: the auth dependency needs `Settings` via `Annotated[Settings, Depends(get_settings)]`, not a plain function parameter with a default — FastAPI otherwise treats any bare Pydantic-model parameter as a second request-body field to embed, which silently turned every request into a 422 regardless of signature. Caught it by manually exercising the endpoint with `TestClient` before writing the formal tests, not by the tests themselves (they were written after the fix). The signature only covers the request body, not headers/method/path, so this doesn't protect against replay attacks (same signed body resent later) — fine for a portfolio project's threat model, but at real scale I'd add a timestamp header into the signed payload and reject requests outside a short window, the way Stripe and Slack do it.
