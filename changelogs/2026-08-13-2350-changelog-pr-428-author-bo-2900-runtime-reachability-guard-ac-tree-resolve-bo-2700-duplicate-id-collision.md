---
title: "Changelog PR #428 — author BO-2900 runtime-reachability guard AC tree; resolve BO-2700 duplicate-id collision"
date: "2026-08-13"
time: "23:50"
type: manual
components: 
  - build_orchestration
  - ac_store
summary: "Authored the acceptance-criteria specification for a new safeguard that stops code from being marked done when nothing in the running system can actually reach it, and cleaned up a duplicate ID collision left over from an earlier merge."
description: "2 commits, PR #428 — docs(build-orchestration): author BO-2900 runtime-reachability guard AC tree (39 files: BO-2900 L0, BO-2900a–f L1, 32 L2/L3), closing the phantom-done gap where PR #411 shipped five AC-lifecycle functions in fast_lane.py with passing covers-tagged tests and zero production callers (done_proof.py::verify_done_eligible only checks that a covers-tagged test exists and passes, not that it runs through the modules entry point). The six L1 guarantees: done-proof requires the proof to run through the entry point; every registered CLI subcommand has a workflow caller; every workflow invocation names a real subcommand; an honest exemption for code with no entry point; a refusal naming the stranded item and the clearing action; a check that never ran is never mistaken for one that passed. fix(ac-store): resolve a duplicate BO-2700 id collision — PR #424 merged docs/acceptance-criteria/build-orchestration/BO-2700-runtime-reachability-guard/ while BO-2700 was already taken by BO-2700-defer-epic-pr (BO-2700a duplicated too); deletes the 13-file duplicate (superseded by the BO-2900 tree, whose f subtree ports those exact files with PR #424 expert-review amendments preserved) and repoints three inbound references (BO-2100d-5, BO-2100a-1-i, BO-2800d). Also adds test_rationale to config/ac_store_schema.json, already used by UXP-600a/UXP-606 and referenced in CLAUDE.md but missing from the schema additionalProperties: false block. Verified: no duplicate ids anywhere in the store; 87/87 AC files valid across the three affected folders; unit_tests/ac_store + unit_tests/commit_guardian: 1559 passed, 5 skipped, 1 xfailed."
pr: 428
commits: 
  - 631ac092a
  - d215e8954
breaking: false
---

## Entry
