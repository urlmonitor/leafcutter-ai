---
title: "KI-TQ-002 — The CI eval job reports missing credentials as a low quality score"
description: "KI-TQ-002 — The CI eval job reports missing credentials as a low quality score"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-10-06'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
---

# KI-TQ-002 — The CI eval job reports missing credentials as a low quality score

> One known issue, split out of `docs/known-issues/testing-quality.md` on
> 2026-09-14. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 3 (2026-08-18; 2026-09-07, see KI-TQ-20260907; 2026-10-06)
- **First seen:** 2026-08-18 · **Last seen:** 2026-10-06
- **Where:** `.github/workflows/agent-evals.yml:71` — `ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}`

**Symptom.** When the `ANTHROPIC_API_KEY` repository secret is unset, the env var is
empty, the `claude` CLI exits non-zero for every row, and each failure is absorbed by the
per-row handler in KI-TQ-001. The job then reports a **quality** verdict — "score 22.22%
below threshold 70.00%" — for a run in which no model was ever invoked. Nothing in the
output says "no credentials". A reader reasonably concludes the agent regressed.

**Evidence.** `Agent evals (affected)` is **not** a required status check. Re-verified
2026-10-06 against ruleset `17810993` (`require-ci-lint`). Its required contexts are exactly
these five: `Lint (ruff)`, `Component vocab style (components.json)`,
`Proof-of-done coverage check (BO-2500b)`, `Changelog entry present` and `AC store valid`.
Until 2026-10-06 this entry also listed `Test suite (pytest)`, which the ruleset does not
require. So this does not block merges — it misinforms. It stays dormant until a PR touches the
trigger closure, then fails on every such PR, and fails dishonestly.

**Fix direction.** Detect the empty-credential case before running any row and fail the
job with an explicit infrastructure error, distinct from a threshold failure. A gate that
cannot run must say so rather than emit a number that looks like a measurement.

**Update 2026-10-06 — fix direction implemented, pending merge.** The owner decided on
2026-10-06 on "Honest failure + narrow", implemented by
`TICKET-20261006-AgentEvalGateHonestAboutCredentials`:
- **Preflight step.** The workflow gains a `Preflight — model credentials` step. When the PR
  affects an agent and `ANTHROPIC_API_KEY` is empty, the job fails before any row runs. It shows
  `::error title=Agent evals - no model credentials::…` and reports no score.
- **Row error.** When the CLI exits non-zero with empty stderr, the row error now carries the
  CLI's stdout `result` text (`Not logged in · Please run /login`) instead of nothing.

The repository still has no `ANTHROPIC_API_KEY` secret (`gh secret list` shows only the three
`LEAFCUTTER_NEO4J_*` secrets), and by the same decision the check stays informational. Move
this entry to `resolved/` once that ticket merges.

---
