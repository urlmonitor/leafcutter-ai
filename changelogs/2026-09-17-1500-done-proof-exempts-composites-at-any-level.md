---
title: "Proof-of-done check treats any AC with child ACs as a composite, whatever its level"
date: "2026-09-17"
time: "15:00"
type: manual
components:
  - build_orchestration
summary: "check-done-proof no longer refuses a done L2 acceptance criterion whose child ACs are all done and covered. An AC is now a composite when its covered_by lists at least one child AC id, at any level. Before, only L0 and L1 counted."
description: "The pre-commit proof-of-done scan in templates/scripts/commit_guardian/check_done_proof.py decided whether an AC was a composite by its level: only L0 and L1 counted. A done L2 parent such as UXP-700d-3, whose children UXP-700d-3-i and -ii are both done and covered, was therefore refused for lacking a covers tag naming its own id, and check-ticket-ac-status-parity then blocked its ticket from closing. The store's own rule in scripts/ac_store/done_proof.py (BO-2500a-6), which mark_ac_done.py uses, is not level-based. The scan now decides by covered_by, both for the staged AC and when recursing into its children. Only entries shaped like AC ids count as children: covered_by in this store also records test file paths, and an entry containing a path separator or ending in .py, .ts or .tsx is not a child. An AC whose covered_by holds only test paths stays a leaf and still needs its own covers tag, with the unchanged message. A composite whose AC children are not all done and covered is still reported, naming the unproven children. AC BO-2500b-1-iii; tests in unit_tests/commit_guardian/test_bo_2500b_1_iii_covered_by_composite.py (5 tests, red before the fix, and mutation-checked by removing the path filtering). check_done_proof.py stays at its existing 663 content lines."
commits:
breaking: false
---

## Entry

A done L2 acceptance criterion whose child ACs are all done and tested can now be
committed as done. The proof-of-done pre-commit check used to accept only L0 and L1
parents. It now treats any AC whose `covered_by` lists child AC ids as a parent,
whatever its level. Test file paths in `covered_by` are not counted as children.
