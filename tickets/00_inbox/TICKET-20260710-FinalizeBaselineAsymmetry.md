---
title: "finalize-feature false test_regression: baseline (step 0) and post-merge (step 3) runs are asymmetric"
status: todo
components:
  - build_pipeline
  - supervisor_system
  - testing_quality
created: 2026-07-10
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
---

# finalize-feature false test_regression: step-0 vs step-3 asymmetry

## Actor / Goal

In order for `/finalize-feature` to actually finish an epic (instead of HALTing on
phantom regressions), its post-merge test run (step 3) must be a valid comparison
against its baseline (step 0) — same test command, same build/deploy state — so only
*real* new failures are classified as regressions.

## Context

Observed repeatedly on 2026-07-10 while finalizing EPIC-PromptAssemblyHardening:
`finalize-feature.js` HALTed **three times** at step 3 with `reason: test_regression`,
each time flagging deploy-dependent AC-schema tests (`test_check_ac_schema.py`,
`test_check_ac_governance.py`, `test_readiness_gate.py`,
`test_check_ac_done_on_merge.py`) as regressions. **Confirmed false**: every flagged
test passes in a built worktree (`test_check_ac_schema.py` 60 passed; `build.py` exit 0;
required gates ruff + schema-diff green). The epic had to be merged + closed manually
(PRs #253, #258) because finalize could not get past its own gate.

Root cause — two asymmetries in `templates/workflows-js/finalize-feature.js`:

1. **Different test commands.** Step 0 (baseline) runs `pytest --tb=no -q` directly in a
   fresh `origin/main` worktree (line ~440). Step 3 (post-merge) dispatches the
   `test-runner` agent to "run the full test suite" (lines ~671–677). These are
   different scopes — any test present in step-3's run but not step-0's is, by
   construction, "not in baseline" → auto-classified `regression` by
   `test-failure-triage`.

2. **No build/deploy before either run.** Neither step invokes `build.py` /
   `install_shims` (grep: zero occurrences). Tests that invoke *deployed*
   `scripts/commit_guardian/…` scripts therefore depend on whatever stale/absent
   deployed artifacts happen to exist in each worktree — the fresh baseline worktree and
   the post-merge worktree differ, so the same test can pass in one and fail in the
   other independent of any code change.

PR #234 ("pre-flight target resolution + **Step 3 build symmetry**", FIN-100g-1/FIN-100a-4)
was meant to address this, but the current script has no build invocation and mismatched
test commands — the fix is **incomplete or regressed**.

Related: the deploy-dependent tests themselves are also tracked in
`TICKET-20260710-PreExistingPytestBaseline.md` (PR #260) cluster 3 — that ticket fixes
the tests/CI; this ticket fixes the finalize workflow's comparison logic.

## Acceptance Criteria

- [ ] AC-1: step 0 (baseline) and step 3 (post-merge) run the **same test command and scope** — the baseline is a valid basis for regression classification.
- [ ] AC-2: both runs execute against the **same build/deploy state** — either both run `build.py`/`install_shims` before pytest, or the tests are made build-independent — so deploy-dependent tests cannot differ purely due to build state.
- [ ] AC-3: with the current known pre-existing failures present, `finalize-feature` classifies them as `pre_existing` (not `regression`) and does **not** HALT at step 3 — verified by a finalize run (or a unit test of the triage against a captured step-0/step-3 pair) on a branch with no real regressions.
- [ ] AC-4: a regression-detection regression test: a genuinely new failure IS still classified `regression` and DOES halt (the gate is not simply disabled).

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

- [ ] Align step-0 and step-3 test invocation (same command + scope) in `finalize-feature.js`.
- [ ] Ensure symmetric build/deploy state before both runs (run `build.py`/`install_shims`, or make the deploy-dependent tests build-independent — coordinate with PR #260 cluster 3).
- [ ] Confirm PR #234's intended "Step 3 build symmetry" is actually present; add it if missing.
- [ ] Add a test proving false regressions no longer halt (AC-3) and real regressions still do (AC-4).

## Risk & Safety

- Touches money? No.
- Touches data? No — changes the finalize workflow's test/triage logic.
- Reversibility? Fully reversible via git. Improves a gate; keep AC-4 to ensure the gate still catches real regressions.
