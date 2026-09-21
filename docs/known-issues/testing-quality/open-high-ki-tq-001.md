---
title: "KI-TQ-001 — An unanswered eval row scores as an all-negative prediction, so a dead agent's floor is not zero"
description: "KI-TQ-001 — An unanswered eval row scores as an all-negative prediction, so a dead agent's floor is not zero"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
---

# KI-TQ-001 — An unanswered eval row scores as an all-negative prediction, so a dead agent's floor is not zero

> One known issue, split out of `docs/known-issues/testing-quality.md` on
> 2026-09-14. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

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
