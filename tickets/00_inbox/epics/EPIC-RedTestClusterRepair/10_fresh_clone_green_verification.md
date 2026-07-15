---
title: "Verify fresh-clone green under strict mode; re-diagnose; hand off to BP-1200b"
status: todo
components:
  - testing_quality
  - build_pipeline
created: 2026-07-15
depends_on:
  - 01_ac_schema_components_and_axes.md
  - 02_create_check_ac_done_on_merge_hook.md
  - 03_agent_template_produces_frontmatter.md
  - 04_commit_classifier_import_cache.md
  - 05_verify_precommit_active.md
  - 06_psutil_dev_dependency.md
  - 07_deployed_plan_feature_e2_parity.md
  - 08_anti_build_shadow_guard.md
  - 09_trustworthy_gate_unmask.md
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
change_target: pipeline
risk_surface: internal
files_touched:
  - debugging/logs/red_cluster_final_diagnosis.md
agents:
  test-writer: not_needed
  python-coder: not_needed
  test-runner: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 10: Fresh-clone green verification + BP-1200b handoff

## Actor / Goal

As a maintainer, I want a single verification pass confirming the suite is genuinely green
on a fresh `origin/main` under strict mode, so we can safely flip the CI gate to blocking
(BP-1200b) without wedging every open PR on residual reds.

## Context

Final ticket of the epic. The failing-test count is a moving target and the review found
that the "green" signal is untrustworthy while AC-enforcement masking is active. Before
BP-1200b flips the gate, someone must confirm — on a fresh checkout, in a fresh process,
under `AC_ENFORCE_STRICT=1` — that the full suite is actually green. This closes the loop
the earlier tickets only gesture at, and verifies the named files and cross-referenced
coverage.

## Dependencies / coverage cross-check (verify, don't re-fix)

- Salvage **PR #300** must have merged (build→build_guards rename, setup_ticket_worktree,
  variant_transform, check_surface_components_e3, skill_registry, build_artifact_parity,
  transform_hooks, 6/7 tracked_source_guard).
- `test_build_tracked_source_guard::…bp900c3` (the 7th) → EPIC-BuildPipelinePhantomRemediation
  ticket 01 (BP-900c-3). Confirm landed.
- `test_check_components_minimum_schema` → already green (1 intentional in-file xfail);
  confirm still green.

## Acceptance Criteria

```gherkin
Given a fresh worktree off origin/main after all epic tickets + PR #300 + the referenced
  phantom-epic tickets have merged
When: build.py runs, then `AC_ENFORCE_STRICT=1 pytest tests/ unit_tests/`
Then the full suite is green (0 failed, 0 unexpected xfail-masked reds) and deterministic
  across two pytest-randomly seeds

Given the named files specifically
Then test_readiness_gate, test_check_ac_done_on_merge, test_build_tracked_source_guard,
  test_generate_ticket_from_ac, and test_check_components_minimum_schema all pass under
  AC_ENFORCE_STRICT=1

Given green is confirmed
Then a short diagnosis note records the result and explicitly authorizes BP-1200b
  (EPIC-BuildPipelinePhantomRemediation ticket 05) to flip the gate; if any residual
  remains, it is filed rather than the gate flipped
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | full suite (strict) | (verification) | |
| AC-2 | 5 named files | (verification) | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

- [ ] In a fresh worktree off origin/main (after deps merged), run build.py then
      `AC_ENFORCE_STRICT=1 python -m pytest tests/ unit_tests/ -q`.
- [ ] Re-run with two `pytest-randomly` seeds to confirm determinism.
- [ ] Confirm each of the 5 named files passes strict; confirm cross-referenced coverage landed.
- [ ] Write `debugging/logs/red_cluster_final_diagnosis.md` with the result; either
      authorize BP-1200b or file the remaining residual.

## Risk & Safety
- Touches money? No.
- Touches data? No — verification + a diagnosis note.
- Reversibility? Fully reversible.
