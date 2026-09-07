---
title: "Fix: done-marking gate no longer refuses genuinely-passing parametrized tests"
date: "2026-09-01"
time: "12:15"
type: manual
components: 
  - ac_store
  - build_orchestration
  - commit_guardian
summary: "Fixed a bug where the tool that decides whether a requirement can be marked done was wrongly refusing requirements whose covering test had actually run and passed, and specified (but did not yet build) a plan to repair stale test-to-requirement links across the store."
description: "Commit 3bba4a9ca fixes done_proof._find_nodeid_for_test, which matched pytest nodeids with `nodeid.endswith(f\"::{func_name}\")` and so never matched a parametrized nodeid (which ends in `[case1]`), returning None and causing a real, passing covering test to be reported as \"linked test not run\" fail-closed. Verified against five real records (ACS-100i-1, ACS-100i-6, ACS-100i-7, BO-2200b-3-ii, BO-2900g-1-i), each now eligible where the unpatched oracle refused it; the same function is imported by fast_lane.py and had no prior test coverage. This falsified ACS-200f (work_status: done). The gate never wrongly granted eligibility, only wrongly refused it. Commits e9b1c0f92 and 0d59af841 add and then correct the figures of a new AC tree, ACS-1300 (20 records), specifying a future covered_by reconciler to repair stale test-to-requirement links; scope is deliberately narrow and does not change mark_ac_done eligibility. Nothing in ACS-1300 is implemented yet -- it is a specification. Also files KI-CG-20260901-covers-regex-truncates-suffixed-ids against check_ac_coverage.py, which collapses suffixed AC ids to their L0 root and misses `//` tags."
pr: 676
commits: 
  - 3bba4a9ca
  - e9b1c0f92
  - 0d59af841
breaking: false
---

## Entry

### The done-marking gate was refusing work it had already verified

The tool that decides whether a requirement can be marked `done` (the "done-proof"
oracle) looks up the pytest result for the test that covers it. That lookup matched a
pytest node id with `nodeid.endswith(f"::{func_name}")`. Pytest emits a **parametrized**
node id as `path::TestClass::test_widget[case1]` — it ends in `]`, not in the function
name — so the match never fired, the lookup returned nothing, and the caller treats "no
match" as fail-closed: a test that had genuinely run and passed was reported back as
`linked test not run`.

In other words, the gate was never letting anything through that shouldn't have been —
it was wrongly **refusing** requirements whose proof was already sitting there, and
naming the wrong reason when it did.

Verified against five real records in the store — `ACS-100i-1`, `ACS-100i-6`,
`ACS-100i-7`, `BO-2200b-3-ii`, `BO-2900g-1-i` — each of which the unpatched lookup
refused and each of which is `eligible=True` after the fix. The lookup function had **no
test coverage anywhere in the repository** before this fix, and it is also used by the
build's fast-lane test-selection path, so that path carried the same defect.

This falsified `ACS-200f` (recorded `work_status: done`), whose own criterion is that the
coverage gate treats a genuinely-passing covering test as passing.

### A specification for repairing stale test links (not yet built)

A new acceptance-criteria tree, `ACS-1300` (20 records), specifies a future reconciler
for the `covered_by` field — the link between a requirement and the tests that prove it.
Measured against the whole store: roughly 549 of 850 tagged records are missing at least
one test that names them, 376 have the link empty outright, and 9 test-path entries name
a file that no longer exists.

This is a specification, not a shipped fix — nothing in `ACS-1300` is implemented yet.
Its scope is deliberately narrow: restoring a missing link will **not**, by itself,
change whether a requirement is eligible to be marked done, because the done-marking
check reads the newer `# covers:` tag first and only falls back to `covered_by` on a
composite record. This tree is about keeping traceability honest, not about unblocking
anything.

A follow-up commit corrected that tree's own reported figures: it first stated "549 of
856," but the re-measured population is 850, not 856 — a new numerator had been paired
with an inherited, stale denominator. Also filed as a known issue:
`KI-CG-20260901-covers-regex-truncates-suffixed-ids` — the coverage-detection regex in
`check_ac_coverage.py` collapses a suffixed AC id to its L0 root and cannot see `//`
tags, so it can credit coverage to the wrong record (detection-only; it cannot block a
merge).
