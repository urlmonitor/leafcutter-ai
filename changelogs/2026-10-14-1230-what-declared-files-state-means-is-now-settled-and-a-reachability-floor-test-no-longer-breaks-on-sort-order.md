---
title: "What declared_files state means is now settled, and a reachability-floor test no longer breaks on sort order"
date: "2026-10-14"
time: "12:30"
type: manual
components: 
  - ac_driven_dev
  - ac_store
  - testing_quality
summary: "The meaning of declared_files[].state, a field nobody had defined, is now settled as a build precondition, and a test that failed whenever a new draft record sorted first no longer does."
description: "PR #1192. One AC-store commit (da19e0b87) plus a test fix in unit_tests/ac_store/test_derived_test_reachability_floor.py. No code or behaviour changed; no gate or validator changed. (1) Acceptance criteria: declared_files[].state is a build precondition, a claim about the tree when this record work is built, not an ownership claim and not a historical snapshot. The proof is the existing enforcement: existing plus absent on an unfinished record refuses the commit, while to_be_created plus present only reports. New draft record ACD-1600c-4-v. ACD-1600c-4 moved done to in_progress because it gained an unfinished child. ACD-1600c-4-i, TQ-600a-13-x and INF-600b-2 amended. (2) Test fix: CI went red on two tests because the real-store anchor was the first record in sort order with a coder agent, no test_spec and two or more Then clauses, and the new draft ACD-1600c-4-v sorted first. As an un-enriched draft it legitimately produces no Test Requirements block, so the test misreported a missing floor. The anchor now also requires the record to declare an implementation .py in its own fields, the condition the generator needs to emit the block, so selection no longer depends on sort order. No assertion was changed; four synthetic tests guard the selector."
pr: 1192
commits: 
  - da19e0b87
breaking: false
---

## Entry

**`declared_files[].state` now has a settled meaning.** It is a build precondition: a claim
about the tree at the moment this record's work is built. It is not an ownership claim and
not a historical snapshot.

- **Proof:** the field's own enforcement already behaved this way. `existing` with the file
  absent, on an unfinished record, refuses the commit. `to_be_created` with the file present
  only reports.
- **Records:** new draft `ACD-1600c-4-v`. `ACD-1600c-4` moved `done` to `in_progress` because
  it gained an unfinished child. `ACD-1600c-4-i`, `TQ-600a-13-x` and `INF-600b-2` were amended.

**A test no longer depends on sort order.** `test_derived_test_reachability_floor.py` picked
its real-store anchor as the first record with a coder agent, no `test_spec` and two or more
`Then` clauses. The new draft `ACD-1600c-4-v` sorted first, and an un-enriched draft
legitimately produces no Test Requirements block, so two tests reported a missing floor. The
anchor now also requires the record to declare an implementation `.py` in its own fields,
which is the condition the generator needs to emit the block. No assertion changed. Four
synthetic tests guard the selector.

No gate or validator behaviour changed, and no code changed.
