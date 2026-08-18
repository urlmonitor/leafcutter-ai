---
title: "goal_to_epic never stamped target_epic — the function was implemented, tested, and never called"
date: "2026-08-18"
time: "11:27"
type: manual
components: 
  - ac_store
summary: "Acceptance criteria pulled into a generated epic were never told which epic they belong to, so the build command could not find them. The code to record that link existed and worked, but nothing ever ran it."
description: "stamp_target_epic() in scripts/goal_to_epic.py was implemented for ACD-1200d-1 and has a passing unit test, but a grep across scripts/ and unit_tests/ finds only two references: the definition at line 1068 and that unit test. There are zero production call sites. Every leaf AC pulled into a generated epic therefore went unstamped, so /build-feature could not resolve those ACs back to their epic. This adds the missing call in run(), immediately after the epic folder is assembled, passing epic_folder.name so the stamp matches the folder /build-feature will actually resolve. Stamping deliberately happens after assembly rather than before, so a failed assembly leaves no back-references pointing at an epic that was never created. Note on why the existing test did not catch this: it exercises stamp_target_epic directly, so it passed green throughout the entire period the function was dead code. A call-site test is what would have caught it, and none exists — this is the dead-code variant of the phantom-done failure mode, where the unit under test is correct and simply unreachable. Known gap, deliberately left out of scope: build_epic_from_ids() (the --ids / fast-lane entrypoint added under BO-2600a-5, assembling at line 2092) also calls assemble_epic_folder and likewise never stamps, so ACs built through the fast lane still receive no target_epic. It is excluded here to keep the change reviewable and because the two entrypoints may warrant different stamping semantics. Provenance: this fix existed as an unpushed local commit (cc19d00d, 2026-06-15) in a consuming repo and was silently lost when that repo advanced its submodule pin to f8cfdfc4 on 2026-08-14 — a local-only fix leaves no trace when the pin moves, no error and no failing test. It is being contributed upstream so the loss cannot recur."
pr: 472
commits: 
  - a2870e38
breaking: false
---

## Entry
