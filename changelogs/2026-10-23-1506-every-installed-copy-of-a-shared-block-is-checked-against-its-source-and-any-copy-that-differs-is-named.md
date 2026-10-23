---
title: "Every installed copy of a shared block is checked against its source, and any copy that differs is named"
date: "2026-10-23"
time: "15:06"
type: manual
components: 
  - build_pipeline
  - build_orchestration
summary: "A new identity check compares every installed copy of a shared block with its rendered source, byte for byte, and names each route, block and line that differs."
description: "Fast-lane build of BO-4500b-2 (branch fastlane/bo-4500b-2). Built acceptance criteria: BO-4500b-2, BO-4500b-2-i, BO-4500b-2-ii. Files changed: scripts/shared_block_identity.py, unit_tests/scripts/_bo4500b2_support.py, unit_tests/scripts/test_bo4500b_2_identity_check.py, unit_tests/scripts/test_bo4500b_2_i_whitespace_drift.py, unit_tests/scripts/test_bo4500b_2_i_crlf_and_newline.py, unit_tests/scripts/test_bo4500b_2_ii_zero_inspected.py, unit_tests/scripts/test_bo4500b_2_deployed_layout.py, unit_tests/build_orchestration/test_bo_4300c_3.py, docs/acceptance-criteria/build-orchestration/BO-4500-fix-once-every-route/BO-4500b-2.yaml, docs/acceptance-criteria/build-orchestration/BO-4500-fix-once-every-route/BO-4500b-2-i.yaml, docs/acceptance-criteria/build-orchestration/BO-4500-fix-once-every-route/BO-4500b-2-ii.yaml."
breaking: false
---

## Entry

A fix to a shared block must reach every route. The install now fills each route's copy from the
block's single source (BO-4500b-1); this change adds the check that proves the copies that are
installed right now still equal that source, including after a hand edit made post-install.

- `scripts/shared_block_identity.py` compares each installed copy with its source as the install
  renders it (the install's own block resolution and placeholder injection), byte for byte. Files
  are read as bytes, so no line-ending or whitespace translation can hide drift.
- A difference is named per route, per block, with the 1-based line of the first difference in the
  installed file. A copy converted to CRLF, a trailing space, a removed blank line and a missing
  final newline are each detected. A route converted to CRLF as a whole file is still inspected
  and reported, not skipped; a START marker with no END, or an END with no START, is reported.
- Consumers are discovered from the markers found in the installed routes, not from a list.
- Inspecting zero copies is a failure and names the location that was searched.
- Blocks declared as awaiting adoption are listed separately and do not fail the check. Hand-kept
  and unknown-block marker pairs are listed in the report and never fail it.
- The suite runs the check against the shared deployed layout with the real build config
  (no build of its own), and `test_bo_4300c_3` now uses this check for its "byte-identical in every
  deployed consumer" test instead of a separate text comparison.
