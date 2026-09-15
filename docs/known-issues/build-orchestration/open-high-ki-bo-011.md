---
title: "KI-BO-011 — A grep-only test aimed at an orphaned file kept a superseded criterion looking satisfied, hiding a direct contradiction between two `done` ACs"
description: "KI-BO-011 — A grep-only test aimed at an orphaned file kept a superseded criterion looking satisfied, hiding a direct contradiction between two `done` ACs"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-011 — A grep-only test aimed at an orphaned file kept a superseded criterion looking satisfied, hiding a direct contradiction between two `done` ACs

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open · the *instance* is covered by the amended **BO-2500d-1** /
  **BO-2500d-1-i** / **BO-2500d-3**; the *class* — an unreachable file serving as a
  criterion's proof — has no AC and is the reason this entry stays open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `unit_tests/workflows/test_bo2500d_gate_retirement.py` (module constant
  `_FAST_LANE_PATH`), against `templates/workflows-js/fast-lane-build.js`

**Symptom.** Two acceptance criteria assert opposite things about the same subject and
both read `work_status: done`. `BO-2500d-1` — *"Opinion-only gate agents are absent from
the fast-lane phase order ... it contains no LLM review agent"* — is contradicted by
`BO-2400f-11`, which puts a `pr-reviewer` dispatch in the fast lane at Phase 4.5, ahead
of `mark_done`. Nothing detected the collision, because `BO-2500d-1`'s entire proof is
~750 lines of string-presence assertions pointed at `fast-lane-build.js`, a file nothing
invokes. The orphan cannot acquire a `pr-reviewer` reference, so the assertions stay
green forever and the criterion reads satisfied no matter what the running lane does.

**Evidence.** `grep -n "pr-reviewer" templates/workflows-js/fast-lane-ship.js` returns
the Phase 4.5 dispatch at line ~700; the same grep against `fast-lane-build.js` returns
nothing, which is exactly what `test_bo2500d_gate_retirement.py` asserts. `BO-2500d-1`
also names the orphan in its `implemented_by`, so a deleted file is a done criterion's
recorded implementation. Three sibling criteria (`BO-2500d-1-i`, `-2`, `-3`) have their
only proof in the same file. Found while sizing `BO-2400c-1-v` (delete the orphan) — the
deletion is what forces the contradiction into the open, and it is blocked until the
`BO-2500d` family is amended.

**Why this is worse than KI-BO-008.** That one is a grep test that constrains the wrong
thing — noisy, but honest about what it looked at. This is a grep test that constrains a
*dead* thing, which is strictly worse than having no test: it does not merely fail to
detect drift, it actively reports that a superseded promise is still being kept. Two
`done` criteria were allowed to contradict each other for roughly four weeks, and the
store showed nothing wrong. Any assertion whose target is a file no code path reaches has
this property, so the orphan is not the interesting part — the aiming is.

**Update, 2026-08-19.** The amendment alone did not settle it. An adversarial review of
PR #510 found that the three amended criteria still read `work_status: done` while their
only proof remained the grep suite above — the branch that amended them never touched
that file, and the executed-behaviour tests their `test_spec` names do not exist. All
three were reset to `in_progress` in that PR. The lesson generalises: amending a
criterion whose proof is a grep does not give it proof, and the store will happily carry
a stronger claim on weaker evidence than it had before.

**Fix direction.** Two separable moves. (1) Reconcile the specs — done in PR #510.
(2) Structural: a test whose only subject is a source file should be detectable as such,
and a source file that no command, workflow, deploy manifest or runtime path reaches
should not be able to serve as a criterion's `implemented_by`. The reachability guard
family `BO-2900` is the natural home; check it before authoring anything new. A cheap
interim: when a criterion's `implemented_by` names a workflow file, assert that file is
reachable from a command template or another workflow.

---
