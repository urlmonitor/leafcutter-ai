---
title: "KI-ACD-006 — A run that authors zero ACs reports `status: \"ok\"`"
description: "KI-ACD-006 — RESOLVED 2026-09-23: a run that authors zero ACs reported status: \"ok\"; all three cancellation exit points in plan-feature.js now return status: \"cancelled\" with cancelled_by: \"person\" attribution."
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-09-23'
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
- **Status:** fixed (2026-08-26, `f1726aef`/PR #602 — predates and is unrelated to the
  ACD-2100 epic; the epic later added `cancelled_by: "person"` attribution on top. See
  "Update — closed" below).
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

**Update 2026-09-23 — closed.** Re-verified directly against the current
`templates/workflows-js/plan-feature.js`, not taken on the epic's own say-so. All three
cancellation exit points now return `status: "cancelled"`, never `status: "ok"`:

- Product-truth gate cancel (`:2843-2850`) — `status: "cancelled"`, `cancelled_at:
  "pt-gate-${ptStep.stage}"`, `cancelled_by: "person"`.
- Mid-pipeline gate cancel (`:3228-3235`) — same shape, `cancelled_at: "gate-${step.stage}"`.
- Final-gate cancel (`:3397-3404`) — same shape, `cancelled_at: "final-gate"`.

The specific symptom this entry recorded — the PT-gate cancel returning `status: "ok"`
for a run that authored zero ACs — is gone; that exact branch now reads `status:
"cancelled"`.

**The `status` fix itself predates the ACD-2100 epic and is unrelated to it.**
`git log -L` on all three call sites traces the `"ok"` → `"cancelled"` change to
`f1726aef` ("fix(build-orchestration): fix the eight defects the red baselines exposed,
and three of the baselines", PR #602, 2026-08-26) — landed the day after this entry was
filed, and confirmed by `KI-ACD-019`'s own `BO-2300a-2` notes as already reopened
(`work_status: todo`) by 2026-08-25 against exactly this code. This register was simply
never updated to close the entry once the fix shipped. The ACD-2100 epic's own
contribution here is narrower: `e5eae49a` ("fix(ac-driven-dev): attribute cancel to the
person and fail closed on a missing final-gate result", part of PR #864) added the
`cancelled_by: "person"` field on top of the already-fixed `status` value.

**Store note for a future reader (not this register's scope to fix).** The AC records
covering this exact behavior, `BO-2300a-1` and `BO-2300a-2`, are still `work_status:
todo`. `BO-2300a-2`'s own notes call the PT-gate fix "observed... incidentally" and
explicitly "unverified against the mid-gate cancel site." This re-verification checked
all three sites directly and confirms the code satisfies them; reconciling the AC
store's `work_status` against that evidence is a separate step this known-issues
register does not perform.

---
