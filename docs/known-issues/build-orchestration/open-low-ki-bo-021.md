---
title: "KI-BO-021 — TODO: `BO-2400e-4` is closed on two of its four specified tests, and the two missing ones are the pair that would survive a writer swap"
description: "KI-BO-021 — TODO: `BO-2400e-4` is closed on two of its four specified tests, and the two missing ones are the pair that would survive a writer swap"
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

# KI-BO-021 — TODO: `BO-2400e-4` is closed on two of its four specified tests, and the two missing ones are the pair that would survive a writer swap

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open — coverage debt, tracked against `BO-2400e-4` (`work_status: done`)
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `unit_tests/build_orchestration/test_ki_bo_003_ac_yaml_preservation.py`; AC at `docs/acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/BO-2400e-4.yaml`

**What is owed.** `BO-2400e-4`'s `test_spec` names four tests. The 14 existing tests supply
two of them (single-record textual diff; field order and untouched text). Two are absent:

1. `test_eleven_member_build_changes_only_its_progress_values` — eleven REAL records copied
   from the store, driven through begin/finish, asserting the total textual change is
   confined to the progress values.
2. `test_progress_recording_preserves_the_record_via_the_real_surface` (angle:
   `reachability`) — drives `claim_build_set` / `release_claim` / `mark_done_built_acs`
   rather than the private helper.

**Why the second one is the point.** Every existing test calls `_update_ac_work_status`
directly. If `BO-2400e-3`'s durable-write work introduces a **new** writer and repoints the
three call sites at it, this suite carries on testing an orphaned function and stays green
while the shape-preservation guarantee is silently gone. `BO-2400e-4`'s own constraint 3
names this outcome ("two writers will drift and one of them will stop preserving") and its
`test_rationale` predicts it verbatim.

**Why it is live rather than theoretical.** `BO-2400e-4` `depends_on: [BO-2400e, BO-2400e-3]`
specifically so that e-3's durable writer would land *first* and this AC would then
constrain it. The build order was inverted — e-4 was satisfied incidentally on 2026-08-18
via KI-BO-003, and e-3 is being built afterwards. The protection the dependency was written
to provide therefore does not exist, and these two tests are what would replace it.

**Sequencing.** Write them **before** the `BO-2400e-3` work merges, so the durable write has
to prove it preserves shape. Landing e-3 first loses the red-baseline evidence that these
tests constrain it.

**Not filed as an AC** because `BO-2400e-4` already specifies both tests exactly; this is
unbuilt work against an existing spec, not a new requirement.

---
