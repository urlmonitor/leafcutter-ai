---
title: "The epic's PR runs green on CI: fix the 99 Linux test regressions, the lint findings and the AC store checks"
status: todo
components:
  - build_orchestration
  - worktree_manager
  - commit_guardian
created: '2026-10-20'
last_updated: '2026-10-20'
depends_on: []
priority: critical
roadmap_phase: phase_1
advances_current_outcome: true
change_target: code
risk_surface: internal
complexity: high
requires_adr: false
requires_diagram: false
tags:
  - BO-4300
  - found-on-pr-1274
files_touched: []
agents:
  test-writer: not_needed
  python-coder: not_needed
  test-runner: not_needed
  pr-reviewer: signed_off
  commit: needed
---

# 18: The epic's PR runs green on CI

## Actor / Goal
In order for the BO-4300 epic (PR #1274) to merge, its required CI checks must pass. Every failing test must be fixed: either the code is fixed, or a test that pins a retired workspace way is migrated to the maker with its promise kept. Never by skipping, xfailing or weakening.

## Context
- **Found:** 2026-10-20 on PR #1274 (branch `epic/every-piece-of-separate-work-gets-its-workspace-v2`, head 0452d88ab).
  - Red: Lint (ruff), AC store valid, and all 8 test shards. There are 100 failing test IDs.
  - Main at the epic's merge base (30bb86622) was green. The same test files against 30bb86622 give 1 failure (`test_acd_2100a_4.py::test_reported_write_failure_matches_what_is_on_disk`), so 99 failures are the epic's.
- **Why it was missed:** each ticket's test-runner compared local Windows failures with the epic's own tip, not with main, so real regressions were filed as "local-only".
- **Linux reproduction:** Docker image `bo4300-ci` (python:3.13 + Node 20 + requirements-dev).
  - Runner: `C:/Users/Hendrik/AppData/Local/Temp/claude/c--Users-Hendrik-Code-leafcutter/95e90780-c7bd-4428-8180-2858f0b19733/scratchpad/ci1274/ci_docker.sh <worktree-bash-path> <pytest args>`.
  - It bundles HEAD, overlays uncommitted files, builds like CI and runs pytest with AC_ENFORCE_STRICT=1.
  - It reproduces CI's 100 failures exactly, in about 80 s.
  - Use it as the source of truth. Windows-local results don't count.

## Scope: three lanes (disjoint files)

**Lane A, plan-feature** (templates/workflows-js/plan-feature.js and its tests):
- Failing tests, about 70:
  - unit_tests/test_plan_feature_pt_phase.py (26)
  - test_partial_run_recovery.py (9)
  - test_final_gate_and_commit_message.py (7)
  - test_commit_stage_output_staging.py and test_commit_stage_output_behavioral.py
  - unit_tests/workflows/test_acd_2100a_1/_4/_5, test_acd_2100c_2/_3/_3_i
  - unit_tests/ac_driven_dev/test_acd_2100a_2_ii_more.py (collection ERROR)
  - unit_tests/ac_driven_dev/rule_check/test_acd_2500a_1.py and test_acd_2500a_1_deploy_declaration.py
- Typical messages:
  - "Expected a real pause_store.py write when the headless run reaches a decision point"
  - "headless discovery must reach paused_awaiting_input … got status error"
  - "no commit agent call"
  - "No 'worktree-setup' dispatch captured"
  - "'it-po' not found in ['shell-runner']"

**Lane B, other workflows** (build-feature, build-ticket, fast-lane-ship and finalize-feature, plus their tests):
- test_finalize_feature_preflight_branch_detection.py (6: pins `git worktree list --porcelain`, `git -C` pre-flight)
- workflows/test_tq_600a_13_xx_finalize_hold.py (3)
- test_bo_1000b_2_i.py (2), test_bo_3800e_1.py (2), test_bo_3800e_2.py (2)
- test_bo2600b_lane_scope_aiming.py (1)
- test_bo2200c5vii_doc_expert_leaf_mode_dispatch.py (2)

**Lane C, config, registry, store and lint:**
- Lint: ruff F401 unused imports in the BO-4300 tests (`ruff check .` reports them; CI lints the whole repository).
- AC tree depth: BO-4300c has 6 L2 children, max 5. BO-4300c-6 was added as an L2 under BO-4300c by the user's choice (2026-10-10). Use the documented `child_limit_override` with a reason citing that decision, or split per the ac-tree-split skill.
- test_artifact_graph_covers_scope.py::test_untagged_done_ac_backlog_does_not_grow (250 > HIGH_WATER_MARK 244): find the done ACs this epic added or flipped without a `# covers:` tag and tag their real proving tests. Never raise the mark.
- test_ge_132a_2_validator.py: it asserts the real declarations; the canary's remedy is author-clears vs an expected mechanical-autofix.
- test_precommit_canary.py::TestHookManifestStages (stages ['pre-commit'] vs ['manual']).
- test_ensure_precommit_config.py::TestManifestIndex0.
- build_guards/test_deploy_collision_guard.py.
- test_bo2400a_1_i_step_kinds_singleton.py: "only the command-step-runner declares step kinds", while shell-runner now does too.

## Rules
- Decide each failure honestly. If the epic's code broke a main behaviour, fix the code. If the test pins a retired workspace way (setup script, worktree-agent, facts/base lookups, `git worktree add/list`, `git -C` commit), migrate it to the maker's shape and keep its promise.
- An AC that genuinely changed needs a user-approved amendment; stop and report instead of editing such an AC.
- Keep the BO-4300f-2 census empty.
- Respect the file-size and complexity ratchets with genuine cuts only. No comment-style tricks.
- Every edited .py must pass `ast.parse` and ruff.

## Acceptance Criteria
- [ ] AC-1: In the Linux container, the 99 epic-caused failures are green, and no new failure appears in the full suite compared with origin/main.
- [ ] AC-2: `ruff check .` is clean, and `python scripts/ac_store/...` (CI's "AC store valid" steps, including check-ac-tree-limits) passes.
- [ ] AC-3: PR #1274's required checks are green.

## Test Requirements

```yaml
tests:
- name: test_hook_manifest_stages
  file: unit_tests/commit_guardian/test_precommit_canary.py
  asserts: An existing red test that this ticket makes green; listed so the build halts on nothing.
  framework: unittest
  type: behavioral
```

## How the work was done

The fixes were made by bug-resolving agents that the coordinator dispatched directly. They ran in three parallel lanes, plus two follow-up tracks and a review-fix pass. The ticket's test-writer, python-coder and test-runner phases were therefore not run as phases, and are marked not_needed.
- **Verification:** every result comes from the Linux container (`bo4300-ci`, CI-like). The coordinator compared the epic's failure list with origin/main at 30bb86622.
- **Review:** pr-reviewer reviewed the full change set (see its comment), and its three medium findings were fixed.
- **User decisions, 2026-10-21:**
  1. re-prove, else retire, the 8 ACs whose code was removed;
  2. canary first in the manifest (BO-1700c-1 amended);
  3. anchor plan-feature's fallback to the in-repo maker;
  4. keep the script steps on worktree-agent, with TICKET-20261021-PlanFeatureScriptStepsToShellRunner as the follow-up;
  5. the re-entrant ADR-051 guard.
- **Commit split:** part 1 (tests only) is 1eccb75c3. Part 2 holds the production changes and AC records.

## Sign-offs
- [x] pr-reviewer — 2026-10-21 09:25
- [ ] commit

## Comments

_(Append-only log — leave blank when authoring.)_

### 2026-10-21 09:25 — pr-reviewer (status: ok)
feedback-id: fb_2026-10-21_b3f1bbd0

Reviewed the 57-file staged diff. No high-confidence findings. Three medium findings:
- M-1 plan-feature.js resolveRepoAnchoredMakerPath: probe 2 (`realpath -- */.git`) takes the alphabetically first child repo with no ambiguity check; with several child repos it can pick the wrong one. It still never runs the untracked-parent copy.
- M-2 BO-1500b-1-i: the new test proves the block/run/negative-control clauses, but not that the config is absent before the maker runs, nor the copy fallback; the AC's test_spec names (4) no longer match the 2 tests.
- M-3 The fail-closed halt of resolveRepoAnchoredMakerPath (no repo found) has no test.
Re-entrant guard is safe: the marker matches only the exact lock path, is consulted only after the lock is found taken, and is inherited only by the holder's children. 18 targeted tests passed locally; the one error was the session-wide guard flagging local remote-ref drift, not the diff.
