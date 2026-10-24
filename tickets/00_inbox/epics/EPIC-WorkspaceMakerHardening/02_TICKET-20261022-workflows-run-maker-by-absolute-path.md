---
title: "Workflows run the maker by its absolute path and stop when a shell step fails"
ac_traceability:
  ac_path: docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces
  l2: []
  l3:
  - BO-4300a-1-ia
  - BO-4300a-1-ib
status: done
ac_coverage: 4/4
components:
  - worktree_manager
  - build_orchestration
created: '2026-10-22'
last_updated: '2026-10-22'
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
change_target: code
risk_surface: internal
complexity: medium
requires_adr: false
requires_diagram: false
tags:
  - BO-4300
  - bo4300-hardening
  - M13
  - M16
  - M5
files_touched:
  - templates/workflows-js/_shared/workspace-answer.js
  - templates/workflows-js/plan-feature.js
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
  - templates/workflows-js/quick-fix.js
  - templates/agents/worktree-agent.md
  - templates/skills/build-feature-ops-notes/SKILL.md
  - templates/skills/ship/SKILL.md
  - templates/workflows/close-worktree.md
  - templates/commands/fast-lane-build.md
  - templates/commands/plan-feature.md
  - templates/commands/quick-fix.md
  - templates/skills/build-single-ticket/SKILL.md
  - templates/skills/feature/SKILL.md
  - templates/skills/plan-feature/SKILL.md
  - templates/skills/quick-fix/SKILL.md
  - templates/workflows/build-backlog.md
  - unit_tests/build_orchestration/test_bo_4300a_1_ia.py
  - unit_tests/build_orchestration/test_bo_4300a_1_ia_lint.py
  - unit_tests/build_orchestration/_bo_4300a_1_ia_fixtures.py
  - unit_tests/build_orchestration/test_bo_4300a_1_ib.py
  - unit_tests/_plan_feature_e2_runner.py
  - unit_tests/_workflow_engine_defaults.py
  - unit_tests/build_orchestration/test_bo_4300a_1_ia_marker.py
  - unit_tests/build_orchestration/test_bo_4300c_4_i.py
  - unit_tests/prompt_assembly/test_build_feature_flatten_wiring.py
  - unit_tests/test_bp_900g_6_paths.py
  - unit_tests/test_finalize_feature_preflight_branch_detection.py
  - unit_tests/test_workflow_dual_engine.py
  - unit_tests/workflows/_bo2400f5iii_fixtures.py
  - unit_tests/workflows/_bo4000_fixtures.py
  - unit_tests/workflows/test_acd_2100a_1.py
  - unit_tests/workflows/test_acd_2100a_5.py
  - unit_tests/workflows/test_bo2400f5iii_declined_step_core.py
  - unit_tests/workflows/test_bo2400f_13_workspace_refusal_workflow.py
  - unit_tests/workflows/test_bo2400f_3_i_worktree_verify_workflow.py
  - unit_tests/workflows/test_bo4000_worktree_reuse_and_naming.py
  - unit_tests/workflows/test_bo_1500a_5_i_dual_engine.py
  - unit_tests/workflows/test_fast_lane_ship_structure.py
  - unit_tests/workflows/test_fin_100h_refusal_not_success.py
  - unit_tests/workflows/test_finalize_feature_preflight.py
  - unit_tests/workflows/test_finalize_pre_merge_safety_gate.py
  - unit_tests/workflows/test_quick_fix_escalation_and_topology.py
  - unit_tests/workflows/test_quick_fix_guard_halts.py
  - unit_tests/workflows/test_quick_fix_worktree_invariant.py
  - unit_tests/workflows/test_tq_600a_13_xx_finalize_hold.py
agents:
  test-writer: signed_off
  llm-expert: signed_off
  python-coder: signed_off
  pr-reviewer: signed_off
  ac-validator: signed_off
  ac-fulfillment-gate: signed_off
  commit: signed_off
---

# 02: Workflows run the maker by its absolute path and stop when a shell step fails

## Actor / Goal
A workflow asks for a workspace with one exact absolute command, so the request works whatever folder the
shell-runner happens to be in. A shell step that gets no real result ends the run. The step is never taken
as having run.

## Context
- **Defect M13 (MEDIUM).** Workflows build the maker command as
  `python3 {{config.output_root}}/scripts/worktree.py ...`. `{{config.output_root}}` renders to the relative
  `.leafcutter`, so the command is cwd-relative.
  - **ACs and decisions violated:** the BO-4300a-1-ia it_requirement "run one exact absolute command
    unchanged", ADR-070 §1.2 and §2.1, and the entry skills' own "never a cwd-relative path" rule
    (BO-4300a-1-ib).
  - **Sites, verified against the current tree:**
    - `build-epic.js:292`
    - `build-feature.js:1522` (the `workspaceConfirmHandedIn` call) and `:1597`
    - `build-ticket.js:1373`
    - `fast-lane-ship.js:773`
    - `finalize-feature.js:448`, `:503` (remove) and `:519`
    - `quick-fix.js:245`
  - **Docs that tell an agent to run `python scripts/worktree.py`:**
    - `templates/agents/worktree-agent.md:85`
    - `templates/skills/build-feature-ops-notes/SKILL.md:209` and `:280`
    - `templates/skills/ship/SKILL.md:18` (locate) and `:52` (remove)
  - **Quoting:** interpolated slugs are unquoted, e.g. `--slug ${epicSlug}` (build-epic.js:292),
    `--slug ${buildSlug}` and `--slug " + finalizeSlug`. Main's KI-BO-20261021 (1f4944742) covers this
    class of bug.
- **Absolute-path resolver:** `resolveRepoAnchoredMakerPath` lives only in `plan-feature.js:2097`. It
  hard-codes `/.leafcutter/scripts/worktree.py`; reconcile that with `{{config.output_root}}` when the
  resolver moves.
- **Defect M16 (LOW).** At `plan-feature.js:2146`, `shellStepDispatch("git branch --show-current", ...)`
  names no location.
  - Its transport failure is caught as best effort (`currentBranchDispatchFailed`, `:2144-2154`).
  - This violates ADR-070 §1.2 ("the command MUST say where it acts") and §5.2 ("no reply ... MUST end the
    run").
  - The same unanchored spelling is the fallback at `:291` and `:1203`.
  - **AC:** BO-4300a-1-ia criteria and IT4 (a declined, prose or empty shell-step answer ends the workflow
    with an error quoting the answer).
- **M5 caller re-check.** Ticket 07 makes `verify` refuse with `VERIFY_FAILED` and moves `kind`, `slug` and
  `branch` to the top level (keeping `marker` as an extra field).
  - `workspaceConfirmHandedIn` / `workspaceVerifyCommand` (`_shared/workspace-answer.js:145-161`) must
    already stop on any non-ok verify answer.
  - `workspaceBranch` (the next function) must read a top-level `branch` first, then fall back to
    `marker.branch`, so that it works before and after ticket 07.
- Workflow tests for this family are Python `unittest` modules that drive the deployed workflows through the
  existing harness (`_bo_4300a_1_ia_fixtures.py`, `_bo_4300c_3_fixtures.py`). There is no JS test runner for
  `templates/workflows-js`.

## Scope
1. Move `resolveRepoAnchoredMakerPath` (and `MAKER_PROBES`) from `plan-feature.js` into
   `_shared/workspace-answer.js`. Every workflow builds each maker command (ensure, verify, remove) from its
   absolute result, quotes every interpolated path and slug, and halts with the resolver's reason when it
   fails.
2. `plan-feature.js`: run the current-branch check as `git -C "<absolute project>" branch --show-current`
   at all three sites. A transport failure ends the run with an error. It is no longer best effort.
3. Rewrite the five doc sites (llm-expert) to the exact absolute form, as BO-4300a-1-ib's entry skills do.
   The form is `python "<absolute install>/scripts/worktree.py" ...`, with the absolute path obtained from
   `worktree.py where` or the resolver. Never a cwd-relative `python scripts/...`.
4. Apply the M5 caller re-check in `_shared/workspace-answer.js` as described in Context.

## Acceptance Criteria
- [x] AC-1: BO-4300a-1-ia ("one exact absolute command, unchanged"). In every deployed workflow, every
  dispatched maker command (ensure, verify, remove) starts with an absolute, quoted path to `worktree.py`
  and quotes every interpolated slug and path. The harness, run from a cwd that is not the project, records
  no maker command with a relative path.
- [x] AC-2: BO-4300a-1-ia IT4 (ADR-070 §5.2). When the current-branch shell step of `plan-feature.js` gets
  no reply (a transport failure), the run ends with `status: error` and dispatches nothing after it. The
  command it sent is `git -C "<absolute project>" branch --show-current`.
- [x] AC-3: BO-4300a-1-ib. No agent, skill or command template under `templates/` tells an agent to run
  `python scripts/worktree.py` or `python3 scripts/worktree.py` by a cwd-relative path; the lint finds zero
  hits.
- [x] AC-4: BO-4300a-1-ia (M5 caller re-check). A handed-in location whose verify answer is
  `refused`/`VERIFY_FAILED` stops the run before any step, quoting the answer. `workspaceBranch` returns the
  top-level `branch` when present, and `marker.branch` otherwise.

## Test Requirements

```yaml
tests:
- name: test_every_workflow_dispatches_the_maker_by_an_absolute_quoted_path
  file: unit_tests/build_orchestration/test_bo_4300a_1_ia.py
  covers:
  - BO-4300a-1-ia
  asserts: >-
    For each deployed workspace-consuming workflow (consuming_workflows()), driven by the existing harness
    from a cwd outside the project, every recorded maker dispatch (ensure / verify / remove) starts with
    an absolute quoted path ending in scripts/worktree.py and quotes its --slug / --path values.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_branch_check_transport_failure_ends_the_run
  file: unit_tests/build_orchestration/test_bo_4300a_1_ia.py
  covers:
  - BO-4300a-1-ia
  asserts: >-
    The deployed plan-feature.js, with the detect-current-branch dispatch made to throw, ends with
    status error and no later dispatch. The command sent carries `git -C "<abs>"`.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_refused_verify_of_handed_in_location_stops_the_run
  file: unit_tests/build_orchestration/test_bo_4300a_1_ia.py
  covers:
  - BO-4300a-1-ia
  asserts: >-
    build-feature.js with args.workspace handed in as a location, and the verify dispatch scripted to
    answer refused/VERIFY_FAILED, stops before any phase dispatch and quotes the answer.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_no_template_runs_the_maker_by_a_cwd_relative_path
  file: unit_tests/build_orchestration/test_bo_4300a_1_ia_lint.py
  covers:
  - BO-4300a-1-ib
  asserts: >-
    A scan of templates/agents, templates/skills, templates/commands and templates/workflows-js finds no
    `python(3)? scripts/worktree.py` and no `{{config.output_root}}/scripts/worktree.py` maker command.
  framework: unittest
  type: behavioral
```

## Sign-offs
- [x] test-writer — 2026-10-22 18:00
- [x] llm-expert — 2026-10-22 19:00
- [x] python-coder — 2026-10-22 12:05
- [x] pr-reviewer — 2026-10-22 23:30
- [x] ac-validator — 2026-10-23 02:00
- [x] ac-fulfillment-gate — 2026-10-22 14:45
- [x] commit — 2026-10-22 23:50

## Comments

_(Append-only log -- leave blank when authoring.)_

### 2026-10-22 18:00 — test-writer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  tests_written_and_red: true
  cross_layer_seam_answer:
    result: covered
    producing_side: "templates/workflows-js/_shared/workspace-answer.js maker-command builders (and the plan-feature resolver moved into it)"
    consuming_side: "each deployed consumer workflow's real shell-step dispatch, observed through the engine harness"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "deployed workflow scripts run through run_workflow_under_e2 (workflow dispatch) with scripted label replies"
red_baseline:
  - test_name: test_every_workflow_dispatches_the_maker_by_an_absolute_quoted_path
    file: unit_tests/build_orchestration/test_bo_4300a_1_ia.py
    kind: assertion
    error: "AssertionError: build-epic.js/ensure: does not start with an absolute, quoted path to scripts/worktree.py: 'python3 .leafcutter/scripts/worktree.py ensure --kind epic --slug stub-user-input' (23 such lines; plan-feature.js/ensure: an interpolated --slug/--path/--ticket value is not double-quoted)"
  - test_name: test_no_deployed_workflow_spells_the_maker_relative_or_unanchored
    file: unit_tests/build_orchestration/test_bo_4300a_1_ia.py
    kind: assertion
    error: "AssertionError: plan-feature.js:1203: branch check names no location; plan-feature.js:2283: relative maker spelling (python3 worktree.py); plan-feature.js:2340: branch check names no location; quick-fix.js:439: relative maker spelling ..."
  - test_name: test_branch_check_transport_failure_ends_the_run
    file: unit_tests/build_orchestration/test_bo_4300a_1_ia.py
    kind: assertion
    error: "AssertionError: 'pause-persist-verify-retry-2' != 'detect-current-branch' : dispatches after the failed step: ['detect-current-branch', 'resolve-maker-path', 'workspace-ensure', ...]"
  - test_name: test_no_template_runs_the_maker_by_a_cwd_relative_path
    file: unit_tests/build_orchestration/test_bo_4300a_1_ia_lint.py
    kind: assertion
    error: "AssertionError: 16 cwd-relative maker spelling(s): agents/worktree-agent.md:85: python scripts/worktree.py ensure --kind <kind> --slug <slug> ..."
  - test_name: test_refused_verify_of_handed_in_location_stops_the_run
    file: unit_tests/build_orchestration/test_bo_4300a_1_ia.py
    kind: assertion
    error: "passes immediately (M5 verify-refusal stop already works)"
    note: "passes immediately -- regression guard, not a red; the abs-path of its verify command is covered by the first test"
  - test_workspace_branch_reads_top_level_branch_then_marker_branch
    file: unit_tests/build_orchestration/test_bo_4300a_1_ia.py
    kind: assertion
    error: "passes immediately (workspaceBranch already reads answer.branch then marker.branch)"
    note: "passes immediately -- regression guard; goes red if marker.branch is preferred over top-level branch"
Tests: unit_tests/build_orchestration/test_bo_4300a_1_ia.py (5 new), test_bo_4300a_1_ia_lint.py (1 new), helpers in _bo_4300a_1_ia_fixtures.py. The harness agent() mock cannot throw, so the transport-failure test runs a copy of the deployed plan-feature.js with a prefix shim that records the call and then rejects. The tests pin the existing label `resolve-maker-path` for the moved resolver and a `git -C "<abs>"` command; verify of a refused answer was already green.

### 2026-10-22 19:00 — llm-expert (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  template_written: true
  prompt_quality_checklist_passed: true
  convention_violations_resolved: true
Rewrote the five doc sites (worktree-agent.md create action; build-feature-ops-notes remedy and baseline; ship locate and remove) to one exact command by the absolute, quoted `<project root>/.leafcutter/scripts/worktree.py` (root from `git rev-parse --show-toplevel`), unchanged, stdout verbatim. Lint test_no_template_runs_the_maker_by_a_cwd_relative_path: only workflows-js hits remain (python-coder).

### 2026-10-22 12:05 — python-coder (status: ok)
feedback-id: (submit-failed)
red_baseline_results:
  - test_name: test_every_workflow_dispatches_the_maker_by_an_absolute_quoted_path
    result: green
  - test_name: test_no_deployed_workflow_spells_the_maker_relative_or_unanchored
    result: green
  - test_name: test_branch_check_transport_failure_ends_the_run
    result: green
  - test_name: test_no_template_runs_the_maker_by_a_cwd_relative_path
    result: green (with llm-expert's doc edits staged in the tree)
  - test_name: test_refused_verify_of_handed_in_location_stops_the_run
    result: green (regression guard)
  - test_name: test_workspace_branch_reads_top_level_branch_then_marker_branch
    result: green (regression guard)
Done: the maker-path resolver (resolve-maker-path probe, MAKER_PROBES) moved into _shared/workspace-answer.js with makerQuote/makerCommand/workspaceEnsure/workspaceConfirmHandedInAt/workspaceMade/workspaceRemoveCommand helpers; all 7 consumer workflows build ensure/verify/remove as `python3 "<abs>/scripts/worktree.py" <verb> ...` with quoted slug/path/ticket; plan-feature's three branch checks are `git -C "<abs>" branch --show-current` and a transport failure ends the run with status error; no bare worktree.py fallback; fast-lane-ship.js comment reworded. File-size ratchet passes.
OPEN (needs test-writer, not python-coder): (1) the engine harness has no default reply for the new `resolve-maker-path` probe in any workflow except plan-feature, so test_each_workflow_receives_answer_or_issues_one_verbatim_maker_request (and other unscripted runs) go red; the fix is one default in unit_tests/_workflow_engine_defaults.py `_default_label_responses_for_script` (stdout `<repo>/.git`); with that default applied locally the 14 test_bo_4300a_1_ia* tests were all green. (2) Existing tests that count/ordered-assert dispatches now see the extra `resolve-maker-path` dispatch before `workspace-ensure` (vs. HEAD, regressions in test_quick_fix_guard_halts, test_bo_3701_build_ticket_dispatch, test_finalize_pre_merge_safety_gate, test_inf_700a_1_v_build_feature_routing, test_bo_3800b_1, test_epic_ticket_set_recheck, test_workflow_dual_engine) and need their expected dispatch lists/counts updated.

### 2026-10-22 13:00 — python-coder (status: ok)
feedback-id: (submit-failed)
Rework: MAKER_SCRIPT_TAIL in _shared/workspace-answer.js is now one plain string constant (the "+" split that dodged the lint regex is removed), with a comment that it is only ever joined to the resolved absolute project root. No tests touched; the lint test is being adjusted by test-writer to recognise this one declared constant.

### 2026-10-22 21:00 — test-writer (status: handoff)
feedback-id: (submit-failed)
(classification: consumer_drift) for the dispatch-count/order updates below; the items under "Not explained by the probe" are reported, not edited.
Harness default: unit_tests/_workflow_engine_defaults.py gives workflows with a workspace step a default `resolve-maker-path` reply (git common dir, `/tmp/harness-default-repo/.git`); the node driver harness unit_tests/prompt_assembly/harness_build_ticket_guard.mjs answers the same label (override: `resolve_maker_path`), not recorded as a phase dispatch, like `workspace-ensure`.
Lint: test_no_template_runs_the_maker_by_a_cwd_relative_path now scans through cwd_relative_maker_hits() (_bo_4300a_1_ia_fixtures.py), which allows only the `const MAKER_SCRIPT_TAIL = "/{{config.output_root}}/scripts/worktree.py";` line in workflows-js/_shared/workspace-answer.js and requires every other mention of the constant there to be `root + MAKER_SCRIPT_TAIL`. New control test_maker_lint_allows_only_the_declared_tail_constant_and_still_catches_relative_paths: a relative `python3 .leafcutter/scripts/worktree.py` in the same file or any other file, the constant declared elsewhere, and an un-joined use are all still reported.
Drift-updated tests (expected dispatches now include the one probe): test_finalize_feature_preflight_branch_detection (3), test_workflow_dual_engine (test_dispatch_order_build_epic, test_dispatch_order_plan_feature; the probe is now first in plan-feature, before detect-current-branch), test_bo_1500a_5_i_dual_engine (same order), test_bo2400f_13_workspace_refusal_workflow (4), test_bo2400f_3_i_worktree_verify_workflow (2), test_tq_600a_13_xx_finalize_hold, test_quick_fix_guard_halts (2), test_quick_fix_escalation_and_topology, test_quick_fix_worktree_invariant, _bo4000_fixtures.RESOLVE_PHASE_LABELS (fixes test_bo4000/a/b/c/d/f phase-call checks), _bo2400f5iii_fixtures.EXCLUDED_LABELS plus a new decline test for the probe (test_declined_maker_path_probe_ends_the_run_quoting_the_reply), test_acd_2100a_5 (its real-shell shim now also executes the shared "Run exactly this one command" shell step). Base-vs-tree Linux run over 260 workflow-loading test files: 282 newly failing ids before, 14 after (the base had 1: test_acd_2100a_4 test_reported_write_failure_matches_what_is_on_disk).
Not explained by the probe (14 ids, tests left as they are):
 - Placeholder in the block: test_bo_4300c_3 test_workspace_answer_block_is_byte_identical_in_every_deployed_consumer (the shared block now holds `{{config.output_root}}`, rendered in deployed copies) and test_acd_2100a_1 test_worktree_step_invocation_is_reached_from_the_workflow_entry_point (source template run unrendered: the command still has `{{config.output_root}}` after the absolute root).
 - Permission gate now after the probe: plan-feature.js dispatches resolve-maker-path and detect-current-branch before the args.workspace_setup_permission checks. test_acd_2100b_5 (2: test_direct_workflow_invocation_with_no_preflight_verdict_halts, test_withheld_permission_still_halts_the_run) use the probe as the "past the gate" marker and assert it is not dispatched when the verdict is missing or withheld. Suggested production fix: move the two permission checks above resolveRepoAnchoredMakerPath.
 - Handed-in workspace from an unrelated, non-repository cwd now runs the probe and halts: test_acd_2100a_5 test_all_three_working_directories_reach_the_first_question and test_no_scenario_halts_before_the_first_question_on_a_missing_file_or_non_repository fail for scenario 'unrelated'.
 - Quoted values and renamed helpers (source-text assertions): test_bo4000_worktree_reuse_and_naming (2, `--slug truthful-project-record` is now `--slug "truthful-project-record"`), test_build_feature_flatten_wiring (workspaceObtain), test_fast_lane_ship_structure (workspaceObtain(), test_fin_100h_refusal_not_success (workspaceDispatch( in the baseline run), test_finalize_feature_preflight (`--slug` in the finalize pre-flight source), test_finalize_pre_merge_safety_gate (2: `worktree.py ensure --kind scratch`, `scripts/worktree.py remove`).

### 2026-10-22 14:00 — python-coder (status: ok)
feedback-id: (submit-failed)
Rework (test-writer's Linux findings), templates/workflows-js only:
1. The shared block is placeholder-free again. MAKER_SCRIPT_TAIL is gone (the lint allowance for it can be removed). Each consumer passes its own rendered output root (`outputRoot: "{{config.output_root}}"` in the ensure/scratch flags, or as the third argument of workspaceConfirmHandedInAt, or to resolveRepoAnchoredMakerPath in plan-feature); the resolver joins `<resolved absolute root>/<output root>/scripts/worktree.py`, with an unrendered template (output root still starting with `{{`) falling back to `.leafcutter`. An absolute output root is used as is.
2. plan-feature.js: the maker resolution and the detect-current-branch step (now `detectCurrentBranch(projectRoot)`) run after the workspace_setup_permission checks, so a missing or withheld verdict halts before any dispatch.
3. With a handed-in workspace (args.workspace answer, or args.worktree_path / workspace_path) the probe is `git -C "<that workspace>" rev-parse --path-format=absolute --git-common-dir` (workspaceAnchor), never the cwd; the child-folder glob probe is not used then. workspaceRemoveCommand now reuses the already resolved maker path (throws if none).
Linux run (ci_docker.sh) of test_bo_4300c_3, test_acd_2100a_1, test_acd_2100a_1_halts, test_acd_2100a_5, test_acd_2100b_5, test_acd_2100b_5_i, test_bo_4300a_1_ia, test_bo_4300a_1_ia_lint: all dots, no failures. File-size ratchet passes for all workflows-js files.

### 2026-10-22 23:00 — test-writer (status: ok)
feedback-id: (submit-failed)
(classification: consumer_drift) Test side finished after the coder's rework (outputRoot passed to the shared helpers, permission gate first, handed-in probe anchored at the workspace).
Lint: the MAKER_SCRIPT_TAIL allowance is removed; cwd_relative_maker_hits() exempts nothing. Control test_maker_lint_exempts_nothing_and_still_catches_relative_paths: relative, bare and output-root-relative maker commands are reported in any file (the shared block included), the absolute quoted form is not.
Source-text drift updated, intent kept: test_bo4000_worktree_reuse_and_naming (`--slug "<slug>"` quoted), test_build_feature_flatten_wiring and test_fast_lane_ship_structure (workspaceEnsure), test_fin_100h_refusal_not_success (workspaceMade), test_finalize_feature_preflight (`slug: finalizeSlug` in the maker request), test_finalize_pre_merge_safety_gate (workspaceMade + kind "scratch"; workspaceRemoveCommand in the cleanup), test_bp_900g_6_paths (the maker path is no longer one literal per workflow: every deployed maker request names the deployed output root and the maker exists there).
test_acd_2100a_1 now renders the workflow with scripts/template_compiler.inject_config and the default config's output_root, as the deployed build does; the production fallback for an output root starting with `{{` can be removed.
test_workflow_dual_engine.py is back to 853 measured lines (four comment banners folded; no assertion touched); test_finalize_pre_merge_safety_gate.py folded two banners to stay within its ratchet.
Linux comparison (base vs tree, 260+ workflow-loading test files): newly failing ids: none (the only failure is the base's test_acd_2100a_4 test_reported_write_failure_matches_what_is_on_disk).

### 2026-10-22 15:00 — python-coder (status: ok)
feedback-id: (submit-failed)
Rework: removed the unrendered-output-root fallback (`{{` prefix meaning `.leafcutter`) from _shared/workspace-answer.js; the resolver now takes the output root as given and rejects a missing one with a reason. Linux run result below in the report.

### 2026-10-22 23:30 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
No high-confidence findings. Medium: M-1 plan-feature branch checks interpolate the project root / workspace path inside double quotes without makerQuote (a `$`, backtick or `"` in the path breaks the command); M-2 ship/SKILL.md step 8 says reuse step 1's maker path but the project root (git rev-parse --show-toplevel) differs between the workspace (step 1) and the main repo (step 8); M-3 a handed-in workspace (clone) anchors the maker to the workspace's own .leafcutter, so a branch-modified maker verifies its own workspace. Tests: drift updates are honest; banner folding touched comment lines only. Details in the reviewer report.

### 2026-10-22 16:00 — python-coder (status: ok)
feedback-id: (submit-failed)
Rework (pr-reviewer mediums): M-3 with a handed-in workspace the maker is resolved from the PROJECT its marker names: one probe `cat "<ws>/<output root>/workspace.json"` (label `read-workspace-marker`), JSON parsed in JS, `<project_root>/<output root>/scripts/worktree.py`; a missing/unreadable marker or no project_root halts via workspaceFailure quoting the reply; never the workspace's own copy; the cwd path is unchanged (`resolve-maker-path`). M-1 every authoringWorktreePath / projectRoot interpolated into a shell command in plan-feature.js goes through makerQuote. M-2 ship/SKILL.md step 8 recomputes the project root with `git rev-parse --show-toplevel` after switching back, with the ONE-exact-command wording. Dead `userIsOnMain` removed. Tests needing a harness default for `read-workspace-marker` (a marker JSON with project_root): see report.

### 2026-10-23 01:00 — test-writer (status: handoff)
feedback-id: (submit-failed)
(classification: consumer_drift) for the marker-step updates; one new test is red on a production finding.
Harness defaults for `read-workspace-marker` (shell reply, stdout `{"project_root": "/tmp/harness-default-repo"}`): unit_tests/_workflow_engine_defaults.py and harness_build_ticket_guard.mjs (override `resolve_workspace_marker`).
Drift updates: test_bo_4300a_1_ia (absolute-quoted-path, refused non-workspace step, refused verify now script the marker via marker_reply()), test_bo_4300c_4_i (marker counted as a preliminary step), test_acd_2100a_5 (the AC workspace gets `.leafcutter/workspace.json` written with the maker's own serializer worktree_paths.portable), _plan_feature_e2_runner.run_isolated_e2 (includes makerQuote in every isolated bundle: fixes test_commit_stage_output_product_truth, 7 tests).
New tests, test_bo_4300a_1_ia_marker.py: (a) missing / declined / non-JSON / project_root-less marker halts every consumer quoting the reply with no maker command dispatched; (b) the verify runs `<project_root>/<output root>/scripts/worktree.py`, the marker read from the workspace; (c) hostile `"`, `$`, backtick workspace path is escaped in the marker read and every `git -C` command.
FINDING (red): test_a_marker_written_the_makers_way_resolves_to_an_absolute_project_path. The real maker stores project_root relative to the workspace (worktree.py _build_marker -> worktree_paths.portable, e.g. `../../fixture/proj`); the resolver uses the value verbatim, so the verify command is `python3 "../../fixture/proj/.leafcutter/scripts/worktree.py" verify ...`, a cwd-relative maker path. Fix in workspace-answer.js resolveMakerFromMarker: resolve a `./` or `../` project_root against the workspace (as worktree_paths.from_portable does) before makerLocation.
Linux comparison (base vs tree, workflow-loading test files plus the new file): newly failing ids: only the red test above. File-size ratchet: harness_build_ticket_guard.mjs compacted to stay at 1000.

### 2026-10-22 17:00 — python-coder (status: ok)
feedback-id: (submit-failed)
Rework: the marker's project_root is stored relative to the workspace (the maker's portable form); resolveMakerFromMarker now resolves a "./" or "../" value against the workspace's absolute path exactly as worktree_paths.from_portable does (new makerPortableToAbsolute in _shared/workspace-answer.js), uses an absolute value as is, and treats a result that is not absolute as a failure quoting the marker reply. Also repaired backslash-class regexes in the same block (path separators) that an earlier edit had flattened. Linux run (ci_docker.sh): test_bo_4300a_1_ia_marker, test_bo_4300a_1_ia, test_bo_4300a_1_ia_lint, test_acd_2100a_5, test_bo_4300c_3 all green.

### 2026-10-22 23:59 — ac-validator (status: blocker)
feedback-id: (submit-failed)
AC coverage incomplete: AC-3 is partial; AC-1, AC-2, AC-4 covered (ac_coverage 3/4). Store alignment script: exit 0.
AC-3 gap: templates/workflows/close-worktree.md:20 (`python scripts/worktree.py locate --kind <kind> --slug <slug>`) and :110 (`python scripts/worktree.py remove --path "<workspace-path>"`) are cwd-relative maker commands. The file is a command-style doc (description frontmatter) outside the lint scan (templates/agents, skills, commands, workflows-js), so test_no_template_runs_the_maker_by_a_cwd_relative_path is green while the ticket intent (no cwd-relative `python scripts/...` anywhere) is unmet. It is not in the staged diff.
Remediation: rewrite both lines to the absolute quoted form like ship/SKILL.md, and widen the lint to all of templates/ (or add templates/workflows). Then re-run ac-validator.
AC-1 covered: impl templates/workflows-js/_shared/workspace-answer.js (makerQuote, resolveRepoAnchoredMakerPath, resolveMakerFromMarker, makerPortableToAbsolute); test test_every_workflow_dispatches_the_maker_by_an_absolute_quoted_path, test_a_marker_written_the_makers_way_resolves_to_an_absolute_project_path, test_a_path_with_quote_dollar_or_backtick_is_one_escaped_word_in_every_command (unit_tests/build_orchestration/).
AC-2 covered: impl plan-feature.js `git -C ${makerQuote(projectRoot)} branch --show-current` (detect-current-branch, plus two authoringWorktreePath sites); test test_branch_check_transport_failure_ends_the_run (test_bo_4300a_1_ia.py).
AC-4 covered: impl workspace-answer.js workspaceConfirmHandedInAt / workspaceBranch; tests test_refused_verify_of_handed_in_location_stops_the_run, test_workspace_branch_reads_top_level_branch_then_marker_branch, test_a_bad_marker_halts_quoting_the_reply_and_dispatches_no_maker_command.
Note: test evidence for the final base-vs-tree comparison was reported by the caller, not verified by me.

### 2026-10-22 19:30 — llm-expert (status: ok)
feedback-id: (submit-failed)
Follow-up: rewrote the two cwd-relative maker commands in templates/workflows/close-worktree.md (locate, remove) to the absolute quoted form with the ONE-exact-command wording; added the file to files_touched. A templates/ sweep found no other unanchored `python ... scripts/worktree.py` command (remaining hits are prose or `<absolute-install-root>`-anchored).

### 2026-10-22 20:00 — llm-expert (status: ok)
feedback-id: (submit-failed)
Follow-up: double-quoted the maker path, --repo-root, --slug and --ticket values in the eight `<absolute-install-root>` maker commands and added the ONE-exact-command wording; files added to files_touched.

### 2026-10-23 02:00 — test-writer (status: ok)
feedback-id: (submit-failed)
Re-ran the Linux comparison after the coder's makerPortableToAbsolute fix and restored separator regexes: base vs tree over the workflow-loading test set plus test_acd_2100b_5 and the new test_bo_4300a_1_ia_marker.py. Newly failing ids: none (the only failure on both sides is test_acd_2100a_4 test_reported_write_failure_matches_what_is_on_disk). The red test_a_marker_written_the_makers_way_resolves_to_an_absolute_project_path is now green. No files changed.

### 2026-10-23 03:00 — test-writer (status: ok)
feedback-id: (submit-failed)
Lint widened (unit_tests only): test_no_template_runs_the_maker_by_a_cwd_relative_path now scans every .md/.js/.mjs/.py/.yaml/.json under templates/ (no folder list), and cwd_relative_maker_hits() also flags an unquoted maker path (UNQUOTED_MAKER_PATH: `python <absolute-install-root>/scripts/worktree.py`, `/abs/...`, `<project root>/...` left unquoted). No file is exempt; quoted absolute forms are recognised by the pattern alone. New control test_maker_lint_covers_every_templates_folder_and_the_docs_absolute_forms: relative and unquoted commands in templates/workflows/*.md are caught, the two documented quoted forms are not. The wider scan finds 0 hits in templates/. Linux: test_bo_4300a_1_ia_lint, test_bo_4300a_1_ia, test_bo_4300a_1_ia_marker all pass (20 passed); ruff and the file-size ratchet clean.

### 2026-10-23 02:00 — ac-validator (status: ok)
feedback-id: (submit-failed)
All 4 ACs covered (ac_coverage 4/4). Re-validation after the AC-3 fix.
AC-3 covered: impl templates/workflows/close-worktree.md:19-21 (`python "<project root>/.leafcutter/scripts/worktree.py" locate --kind <kind> --slug "<slug>"`, staged); a grep of templates/ finds no unquoted or cwd-relative `python scripts/worktree.py`; test test_no_template_runs_the_maker_by_a_cwd_relative_path now scans every text file under templates/ (test_bo_4300a_1_ia_lint.py), plus test_maker_lint_covers_every_templates_folder_and_the_docs_absolute_forms.
AC-1, AC-2, AC-4 covered as in the earlier blocker comment above. The caller reports the base-vs-tree comparison shows no newly failing ids; not re-run by me.

### 2026-10-22 14:45 — ac-fulfillment-gate (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  ac_store_fields_verified: true
  ac_yaml_schema_valid: true
BO-4300a-1-ia and BO-4300a-1-ib (both L3 leaves) were already work_status: done; the resolver reports ok for both. Appended covered_by (only files with a matching `# covers:` tag): ia += test_bo_4300a_1_ia_marker.py, workflows/test_bo2400f5iii_declined_step_core.py; ib += test_bo_4300a_1_ia_lint.py (its ib-tagged tests). Appended ib implemented_by: templates/skills/ship/SKILL.md, templates/skills/build-feature-ops-notes/SKILL.md, templates/agents/worktree-agent.md, templates/workflows/close-worktree.md, templates/workflows/build-backlog.md. check_ac_schema.py exit 0 on both; both files staged. mark_ac_done.py --test-root: ib first errored (pytest timeout), re-run reported no-op (already done), and its linked tests pass. ia was REFUSED locally: test_a_marker_written_the_makers_way_resolves_to_an_absolute_project_path fails on this Windows host (worktree_paths.portable returns a POSIX path unchanged, so the fixture is not relative); it is the known Windows-only trap and Linux runs recorded above passed. ia work_status left as it was (done). Parent BO-4300a-1 not touched.

### 2026-10-23 04:00 — test-writer (status: ok)
feedback-id: (submit-failed)
test_a_marker_written_the_makers_way_resolves_to_an_absolute_project_path now builds project and workspace as real directories under a tempfile root, so worktree_paths.portable() yields the relative `../` form on Windows and Linux; the resolved maker path is asserted against that real project root, separator- and case-normalised (os.path.normcase). Passes locally on Windows (4 passed) and on Linux via ci_docker.sh; ruff and complexity (<= 15) clean.

### 2026-10-22 23:50 — commit (status: ok)
feedback-id: (submit-failed)
Committed the staged set (52 files) with pre-commit hooks active; probe passed.
