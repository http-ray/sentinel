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
