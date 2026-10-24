---
title: "plan-feature.js gets back under its file-size limit"
status: todo
components:
  - ac_driven_dev
created: 2026-10-23
last_updated: 2026-10-23
depends_on: []
priority: medium
roadmap_phase: phase_1
change_target: code
risk_surface: internal
requires_diagram: false
requires_adr: true
tags:
  - size-ratchet
  - follow-up-of-pr-1315
agents:
  architect-review: needed
  test-writer: not_needed
  python-coder: needed
  test-runner: needed
  pr-reviewer: needed
  commit: needed
---

# plan-feature.js gets back under its file-size limit

## Actor / Goal
In order for changes to `/plan-feature` to land without skipping the size hook, `templates/workflows-js/plan-feature.js` must shrink below its measured limit, so that fixes pay for themselves again under the 2-for-1 rule.

## Context
- **Found:** 2026-10-23, building PR #1315 (ACD-300a-3, ACD-2500a-2-ix-a, ACD-300g-1-i, ACD-300g-4, ACD-300c-3, ACD-300c-5).
  - The file measured 2525 lines before those fixes. They add a net 37 measured lines, so the hook wanted 2467 or below, about 95 lines removed.
  - Moving comment blocks to docs saves only (n-1) lines per block, and the rationale comments are already one-line pointers.
  - **User decision 2026-10-23 ("Skip the hook once"):** the #1315 commit ran with `SKIP=check-file-size`. This ticket pays that debt back.
- **Constraint:** E2 workflow bodies are self-contained and cannot `require`/`import` local modules (see the notes in `finalize-feature.js` and `build-feature.js`). A plain module split does not work.
- **Precedent:** BO-3900 skipped the same hook on this file for a path fix.

## Acceptance Criteria
- [ ] AC-1: `check-file-size` passes on `templates/workflows-js/plan-feature.js` with no skip.
- [ ] AC-2: The `/plan-feature` behaviour is unchanged: the plan-feature workflow tests under `unit_tests/workflows/`, `unit_tests/ac_driven_dev/` and `unit_tests/test_final_gate_and_commit_message.py` pass as before.
- [ ] AC-3: An ADR records the chosen way of shrinking the file, so other over-limit workflow scripts can follow it.

## Implementation Tasks
- [ ] Choose a route (architect-review). Candidates:
  - (a) Move pure, deterministic helpers (message builders, resume-scan parsing) into a Python script the workflow calls through a script step, as `requirement_rule_check.py` and `approve_acs.py` already are.
  - (b) Build-time inclusion: `scripts/build.py` concatenates shared JS fragments into the deployed workflow; the size limit applies per source fragment.
  - (c) Split `/plan-feature` into two workflows (authoring stages; test design, hand-back and final gate) joined by the existing pause/resume record.
- [ ] Implement the chosen route with verbatim moves only.
- [ ] Rebuild and run the tests above.

## Risk & Safety
- Touches money? No.
- Touches data? No. AC-store writes keep their current path through the stage commits.
- Reversibility: full; this is a pure refactor.
