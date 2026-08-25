---
title: "Known issues — testing-quality"
description: "Open, observed defects in the testing-quality component: the agent eval harness, its scoring and threshold gates, and the CI job that runs them. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-08-18
components:
  - testing_quality
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/how-to/prove-ac-done.md
---

# Known issues — testing-quality

Observed defects in this component that are **not yet fixed**. This file exists so a
defect noticed in passing can be recorded in seconds, without authoring a full
acceptance criterion for something nobody has decided to build yet.

## How to use this file

**Read it before adding new capability to this component.** Fixing what is already
broken takes precedence over building more.

**Adding an issue.** Append a new `### KI-TQ-NNN` section using the next free number.
Nothing here is generated — edit it by hand. Fill in what you actually know; an issue
recorded with a thin `Evidence` line is far better than one not recorded.

**Hitting an existing issue.** Increment `Occurrences` and update `Last seen`. Do not
add a duplicate entry. Occurrences is an escalator, not the score — a blocker seen once
outranks an annoyance seen ten times.

**Severity** is `blocker` (work cannot land) / `high` (silent wrong behaviour) /
`medium` (real but survivable) / `low` (noise, dead code, cosmetics).

**Closing an issue.** When the fix lands, delete the section and reference the issue id
in the commit message. If it earns real work, author an AC for it and note the AC id in
`Status` — this file is a capture surface, not a replacement for the AC store.

---

### KI-TQ-001 — An unanswered eval row scores as an all-negative prediction, so a dead agent's floor is not zero

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `scripts/evals/run_agent_eval.py` — label-mode row loop, the `ModelInvocationError` handler

**Symptom.** When a model call fails or its reply cannot be parsed, the handler logs a
WARNING and sets `predicted = {}`. An empty prediction is then scored as *every axis
False*. For any gold row whose labels are all False, that is a **correct** answer. So a
row that never received a model answer can be recorded as a pass, and an agent that is
completely dead does not score 0% — it scores the all-negative fraction of its gold set.

**Evidence.** In a **locally passing** `pt-classifier` run (88.89%, threshold 70), rows
`clf-012` and `clf-014` each logged `model invocation/parse failed: No JSON object found
in model reply` and still printed `[PASS] ... exp=none got=none`. Two of the sixteen
"passes" had no model answer behind them; the honest figure is 14 of 16 answered rows.

The same arithmetic explains KI-TQ-002: the `pt-classifier` gold set has 4 all-negative
rows out of 18, and 4 ÷ 18 = 22.22% — exactly the score CI produces when no credentials
are present.

**Fix direction.** Treat a row carrying `parse_error` as **unscored** rather than as a
prediction: exclude it from the accuracy denominator and fail the run when unscored rows
exceed a small tolerance. Separately, an eval's floor should be stated explicitly —
compute the all-negative baseline for each gold set and require the configured threshold
to sit above it, so a threshold can never be cleared by silence.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M6.

---

### KI-TQ-002 — The CI eval job reports missing credentials as a low quality score

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `.github/workflows/agent-evals.yml:71` — `ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}`

**Symptom.** When the `ANTHROPIC_API_KEY` repository secret is unset, the env var is
empty, the `claude` CLI exits non-zero for every row, and each failure is absorbed by the
per-row handler in KI-TQ-001. The job then reports a **quality** verdict — "score 22.22%
below threshold 70.00%" — for a run in which no model was ever invoked. Nothing in the
output says "no credentials". A reader reasonably concludes the agent regressed.

**Evidence.** `Agent evals (affected)` is **not** a required status check. Verified
2026-08-18 against ruleset `17810993`, whose required contexts are exactly: `Lint (ruff)`,
`Component vocab style (components.json)`, `Test suite (pytest)`,
`Proof-of-done coverage check (BO-2500b)`, `Changelog entry present`, `AC store valid`.
So this does not block merges — it misinforms. It stays dormant until a PR touches the
trigger closure, then fails on every such PR, and fails dishonestly.

**Fix direction.** Detect the empty-credential case before running any row and fail the
job with an explicit infrastructure error, distinct from a threshold failure. A gate that
cannot run must say so rather than emit a number that looks like a measurement.

---

### KI-TQ-003 — The eval staleness gate asks you to stage a file that is gitignored

- **Severity:** low
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/scripts/commit_guardian/check_eval_staleness.py:156` (a commit-guardian hook, filed here because its subject is the eval workflow); `scripts/evals/results/.gitignore`

**Symptom.** On a stale result the hook prints `Re-run the affected eval(s) locally, then
re-stage the result:`. Re-staging is impossible: `scripts/evals/results/.gitignore` is
`*.json`, so no result file can ever enter the index.

**Evidence.** The gate nonetheless works, because `eval_selector.py` reads the result from
disk rather than from the index. Only the remediation message is wrong — which makes it a
documentation defect that costs the next person a confused minute, not a correctness one.

**Fix direction.** Reword the message to "re-run the eval so the on-disk result is fresh";
drop the staging instruction.
