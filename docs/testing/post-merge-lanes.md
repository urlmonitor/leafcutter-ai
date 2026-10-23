---
title: Post-merge Lanes and Where Each Test Runs
type: reference
status: active
created: 2026-10-23
last_updated: 2026-10-23
components:
- testing_quality
related_docs:
- docs/testing/README.md
- scripts/suite_performance/README.md
- docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xxvi.yaml
description: "The post-merge lanes (correctness, live database, timing), the three places the live-database tests run and what each means, and how a live-lane failure or unreachable database ends the run."
---
# Post-merge Lanes and Where Each Test Runs

Tests excluded from the default run are not dropped; the post-merge workflows run them
(and the live-database tests in full) after every merge to main and on the 12-hour
heartbeat (cron `17 3,15 * * *`). Every lane retries failing tests once on a fresh runner
before reporting a verdict.

| Lane | Workflow | Selects | On failure |
|------|----------|---------|------------|
| Correctness | `Post-merge suite` (jobs `run`, `retry`) | `_MANUAL` tests (`-m "manual and not timing_ratio"`) | Opens or updates the `post-merge-red` issue. The `Post-merge suite status` check holds pull requests while the run is red, did not complete, or is stale (over 30 hours). It is not a required check yet. |
| Live database | `Post-merge suite` (jobs `live_run`, `live_retry`) | The whole `tests/knowledge_live/` folder, against three disposable `neo4j:5.26-community` services (ports 17687, 18087, 18088) | Shares the one combined verdict with the correctness lane, so it holds pull requests the same way. |
| Timing | `Post-merge timing suite` | `timing_ratio` tests (wall-clock ratio assertions) | Opens or updates the separate `post-merge-timing` issue, which names tests that newly entered the lane and the commit that touched them. It never holds a pull request. |

## Where the live-database tests run

The live-database tests (`tests/knowledge_live/`) run in three places with three meanings:

- **Per-PR test shards** (`ci.yml`, `test-shard`): skipped, because the shards start no database.
- **Pull request Proof-of-done** (`ci.yml`, `done-proof`): the job starts the three disposable databases on every pull request and runs the live tests of the criteria that pull request changes. The post-merge live lane does not change it.
- **Post-merge run**: the whole folder, after every merge to main and on the heartbeat.

## How the live lane ends

- A test that fails twice (first run and the one retry) turns the combined verdict red.
- A database that is unreachable or never became healthy ends the lane as did-not-complete, not red.
- A skip is never counted as a pass.
- A fix proof for a red live lane starts the same three databases (`post-merge-fix-proof.yml`).

## Moving a test between lanes

Adding `@pytest.mark.timing_ratio` to a test moves it out of the default run and out of
the holding correctness lane into the timing lane. That is a reviewed change: name the
test in the PR. Opt in locally with `python -m pytest -m timing_ratio <path>` (or
`-m manual` for the correctness lane).

## See Also

- [Portable Testing Conventions](README.md) — the `Post-merge suite status` hold messages and the break-glass procedure
- [scripts/suite_performance/README.md](../../scripts/suite_performance/README.md) — how the `_MANUAL` exclusion works
