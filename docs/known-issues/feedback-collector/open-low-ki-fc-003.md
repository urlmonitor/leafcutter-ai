---
title: "KI-FC-003 — `ac-validator` is in no category's `allowed_writers`, so it has never submitted a single feedback record"
description: "medium — silent, and it invalidates the corpus rather than just losing one record"
type: reference
category: reference
status: active
created: '2026-08-25'
last_updated: '2026-08-25'
components:
  - feedback_collector
related_docs:
  - docs/known-issues/feedback-collector.md
  - docs/known-issues/README.md
---

# KI-FC-003 — `ac-validator` is in no category's `allowed_writers`, so it has never submitted a single feedback record

> One known issue, split out of `docs/known-issues/feedback-collector.md` on
> 2026-09-14. Index: [feedback-collector.md](../feedback-collector.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium — silent, and it invalidates the corpus rather than just losing one record
- **Status:** open — code and config are on `main` and live
- **Occurrences:** 2 (2026-08-19; 2026-09-07, where it also caught a **second** affected agent)
- **First seen:** 2026-08-19 · **Last seen:** 2026-09-07 (re-verified against `e5bb41b6d`)

> **Second occurrence, 2026-09-07 — and the gap is wider than one agent.** Hit again while
> closing out GE-120's outstanding phases. Re-verified: `grep -c 'ac-validator'
> config/feedback_categories.yaml` → **0**, against **19** for `pr-reviewer` /
> `documentation-verifier`, so this is a per-agent omission rather than a broken file.
>
> **`ac-fulfillment-gate` is affected too** — it is likewise in no category's
> `allowed_writers`, and recorded `(submit-failed)` on the same run. Both are *required*
> phase agents in the sign-off chain, and both are the AC-coverage gates specifically: the
> two phases whose feedback is most worth having is exactly the feedback the corpus has never
> received. Any remediation should register both, and should check the rest of the phase
> roster rather than fixing the two that happened to be observed — the same
> "fix the instances you caught, miss the class" shape as
> `KI-CG-20260831-hook-scripts-never-invoked`.
- **Where:** `config/feedback_categories.yaml` — the nine `allowed_writers` lists (lines 30, 56,
  82, 91, 119, 147, 176, 185, 212); `scripts/feedback/submit_feedback.py`

> **Recovered from an unmerged branch.** Recorded as `KI-FC-1` in PR #495's parallel
> known-issues register, which was discarded during reconciliation. Re-verified before filing:
> `grep -n 'ac-validator' config/feedback_categories.yaml` still returns **nothing**.

**Symptom.** `ac-validator` is absent from `allowed_writers` in every category.
`submit_feedback.py` therefore rejects it for **every** category, and the agent falls back —
correctly, per the `signoff` skill — to recording `feedback-id: (submit-failed)` and continuing,
because a failed submit is explicitly not a phase failure.

Found on 2026-08-19 when `ac-validator` signed off `GE-122e-2` and reported that every category
had been refused.

**Why this is worse than a lost record.** It is not intermittent. Every `ac-validator` run since
the allowlist was written has contributed **nothing**, so any analysis of the feedback corpus
silently under-represents AC-coverage findings — and reads as *"ac-validator rarely has anything
to report"* rather than *"ac-validator has never been able to report"*. The absence is
indistinguishable from a quiet agent, which is why nine months of runs produced no signal that
anything was wrong.

**Root cause.** Two lists that must agree — the agent registry and the feedback allowlist — with
nothing checking that they do. The file's own decision history shows this is the recurring
failure mode, not a one-off: `user-surface-smoker` (2026-06-03), `frontend-coder` and
`llm-expert` (2026-06-08), and `documentation-verifier` (2026-07-17) were each added
retroactively after the same silent rejection was noticed by hand. `ac-validator` is the fifth.

**Detection.** Grep the corpus for the agent name; an agent with zero entries across many runs is
the tell. Or check membership directly:

```bash
grep -n "allowed_writers" -A 20 config/feedback_categories.yaml
```

**Fix direction.** Add `ac-validator` to the appropriate categories — but that is the fourth
instance of the same manual patch, so it is the smaller half. The useful fix is a build-time or
startup consistency check that every agent with `signoff: true` in `config/agent_registry.json`
appears in at least one category's `allowed_writers`. The general defect is that the two lists
can disagree with nothing noticing.

**Pattern:** the same silent-gate shape as the commit-guardian register's `KI-CG-024` — exit 0, a
fallback that keeps the pipeline moving, and no signal that a capability is entirely absent.
