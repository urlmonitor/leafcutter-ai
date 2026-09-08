---
title: "47 orphans are four populations, not one — and the existing repair tool would fix the wrong six"
date: "2026-09-08"
time: "10:55"
type: manual
components:
  - ac_store
  - commit_guardian
summary: "Specified (not yet built) the plan to close the AC store's orphaned-child gap: an orphan silently shrinks the evidence a parent's done claim is checked against, and today's 47 orphans split into four populations with opposite correct handling — most notably six that must never be repaired and a repair script that would repair them anyway."
description: "Adds new L0 ACS-1400 (four L1s, 19 leaves, all readiness: draft) to docs/acceptance-criteria/ac-store/. Nothing is repaired or enforced by this commit — it is specification only. Investigation findings recorded in the ACs: the 47 orphans are 6 deliberate exclusions (KM-200a-f) that must stay unlinked, 25 test-paths-only parents where appending a child flips a leaf/composite classification, ~5 superseded-by parents of unclear convention, and ~10 plain drift. fix_ac_orphans.py currently repairs all 47 indiscriminately, including its --dry-run output. check_ac_parent_covered_by has three exit paths whose silence means three different things; measured against the real deployed hook (via HOOK_TEST_FILES, not argv), the undocumented depends_on-based escape hatch alone silences 26 of the 47."
breaking: false
---

## Entry

### What this commit is, and is not

This lands a new L0, `ACS-1400`, with four L1s and 19 leaves — all `readiness: draft`.
**Nothing is repaired here, no hook behaviour changes, and no orphan is fixed.** This is
the specification pass; ACS-1400a/b/c/d are what will eventually do the work.

### Why an orphan is not cosmetic

`covered_by` is the evidence a parent's `done` claim is checked against. When a child
exists but its parent's `covered_by` doesn't list it, the store silently narrows what it
believes it has to prove — and `check_done_proof` compares only what's in the commit
index, so it has no way to notice. `ACD-400a` carried exactly this: stale by two children
for five days, claiming done with both listed children still `todo`, and every commit in
that window passed every AC hook.

### "47 orphans" is four populations with opposite correct actions

At most ~10 of the 47 are the drift the number suggests.

| Count | Population | Correct action |
|---|---|---|
| 6 | `KM-200a`–`f` | **Must never be repaired.** Empty `covered_by` is deliberate under the cheap-capture convention; repairing injects six unready L1s into the buildable backlog. |
| 25 | test-paths-only parents | Appending a child id flips `_has_resolvable_child` from leaf to composite, changing what the store believes can be finished. ACS-1400c abstains on these explicitly. |
| ~5 | parents that are themselves `superseded_by` | `TKT-100` omits two retired L1s its successors replaced — reads deliberate, but `ac-schema.md`'s status lifecycle is silent on the convention, so ACS-1400c-4 gates on ruling it one way or the other. |
| ~10 | plain drift | `BO-100d` (4), `FIN-100h` (1), `UXP-4xx` (5) — the only population a blind append would have been correct for. |

### The existing repair tool would do the wrong thing

`fix_ac_orphans.py` already exists and appends every orphan to every parent with no
adjudication. Run today, it "repairs" all 47 — including the six that must never be
touched. Its `--dry-run` prints the same unsafe plan, so even the cautious path
recommends the damage. The gap was never that reconciliation is impossible; it is that
reconciliation is one command away and that command is unsafe. ACS-1400c's deliverable is
the adjudication, not the write.

### The guard's silence means three different things

`check_ac_parent_covered_by` has three escape hatches, not the one paths documented
elsewhere describe: staged-set only; parent-absent fails open with a warning; and an
undocumented third — it returns clean unless the ID-derived parent also appears in the
child's own `depends_on`. Measured by invoking the real deployed hook once per orphan
through `HOOK_TEST_FILES` (not argv, which several of these hooks ignore entirely), the
undocumented hatch alone silences 26 of the 47 — a majority, for whom staging the parent
would have changed nothing.

### Two anti-vacuity constraints carried into the spec

- "Done" is **not** zero orphans. A store reporting six labelled exclusions is healthy;
  binding success to zero forces the six wrong repairs.
- Every safety guarantee is satisfied by a tool that does nothing, so each must be
  asserted in the same invocation as a repair that genuinely happened — guarding against
  a fix that passes by staying inert.

### Sequencing note

`ACS-1400a` strengthens the same file `ACS-1200a` adds a parked-tree exemption to, and is
recorded as a strict prerequisite (not a courtesy): the guard already blocks all six
`KM-200` children today, so the wrong verdict is already live.

### Validated

`OK: all 341 AC YAML files are valid.` Orphan scan still reports 47, zero of them
`ACS-1400` — the new records added none of their own.
