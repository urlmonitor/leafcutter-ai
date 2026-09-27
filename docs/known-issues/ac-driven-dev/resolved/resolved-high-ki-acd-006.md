---
title: "KI-ACD-006 — A run that authors zero ACs reports `status: \"ok\"`"
description: "KI-ACD-006 — A run that authors zero ACs reports `status: \"ok\"`"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-09-25'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/README.md
---

# KI-ACD-006 — A run that authors zero ACs reports `status: "ok"`

> One known issue, split out of `docs/known-issues/ac-driven-dev.md` on
> 2026-09-14. Index: [ac-driven-dev.md](../../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** **RESOLVED** (`f1726aef`, PR #602, under AC `BO-2300a-2`; verified 2026-09-25 by
  reading all three cancel returns on main `d2fe85a1` and running
  `unit_tests/workflows/test_bo_2300a_2_cancel_status_distinct.py` — 2 passed)
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/workflows-js/plan-feature.js` — cancellation return path

**Symptom.** The cancelled run returned:

```json
{"status": "ok",
 "message": "Pipeline cancelled at the product-truth gate (mock-data-author).
             No PR was opened. ...",
 "cancelled_at": "pt-gate-mockdata"}
```

`status: ok` for a run that produced no ACs, opened no PR, and left a draft stranded.
A caller that branches on `status` — which is the whole point of returning one — treats
this as success. Verified independently: the authoring worktree
`worktrees/guardrail-engine` had **zero commits** and **zero AC files** afterwards.

**Fix direction.** `ok` should mean "the thing you asked for happened". A cancellation
is `cancelled`; a cancellation nobody asked for is an `error`. This is the same
false-success class as `build-feature` reporting `status: ok` with `skipped_phases: []`
while never opening a PR — see `docs/known-issues/build-orchestration.md` KI-BO-001 for
the sibling shape in the other workflow.

## Resolution

Fixed in `f1726aef` — *fix(build-orchestration): fix the eight defects the red baselines
exposed, and three of the baselines (#602)*, 2026-08-26 — under AC `BO-2300a-2` ("distinct
terminal status for a cancelled run"). Follow-ups `e3aa88c2` / `dfead426` added
`cancelled_by: "person"` to the same returns (ACD-2100c-5). The entry sat at `open` for a
month after the fix.

Verified 2026-09-25 on main `d2fe85a1`:

- `templates/workflows-js/plan-feature.js` — every user-cancel return now reports
  `status: "cancelled"`, never `"ok"`:
  - `:2844` PT gate (`cancelled_at: pt-gate-${ptStep.stage}`) — the exact path in the Symptom;
  - `:3229` per-stage AC gate (`cancelled_at: gate-${step.stage}`);
  - `:3398` final gate (`cancelled_at: "final-gate"`).
- The "cancellation nobody asked for" half of the fix direction is also in place: a
  null/unusable gate reply returns `status: "error"` with "gate failure, NOT a user
  cancellation" (e.g. `:2818`–`:2831`, `:3181`–`:3191`) instead of entering the cancel branch.
- `python -m pytest unit_tests/workflows/test_bo_2300a_2_cancel_status_distinct.py -q` →
  `2 passed`. `test_ac2_pt_gate_cancel_status_is_distinct_from_ok` drives a real
  `{"action": "cancel"}` at `pt-gate-mockdata` — this entry's own repro — and
  `test_ac2_midgate_cancel_status_is_distinct_from_ok` does the same at `gate-ba`.
  `PYTHONUTF8=1 python -m pytest unit_tests/test_plan_feature_pt_phase.py -k
  test_cancel_no_pr_prior_commits_preserved -q` → `1 passed` (asserts
  `status == "cancelled"`, `cancelled_at == "pt-gate-mockup"`). Without `PYTHONUTF8=1`
  on Windows that suite fails with a `cp1252` `UnicodeEncodeError` in the test harness's
  stdin write, which is unrelated to this defect.

Not part of this defect, noted for completeness: the **covered-route** prompt (`:2666`)
still returns `status: "ok"` when the user picks `cancel` there. That choice means "the
existing ACs already cover this request", so `ok` is arguably the correct outcome rather
than a false success. The uncommitted draft left after a PT cancel is the intended
NO-PR guarantee (prior committed stages kept, current draft left on disk), not a strand.

---
