---
title: "The workspace maker builds every workspace pointing at the project's durable log root, and main's tests reach the maker"
ac_traceability:
  id: INF-500d-4-iii
  path: docs/acceptance-criteria/infrastructure/INF-500-operational-observability/INF-500d-4-iii.yaml
status: done
ac_coverage: 4/4
components:
  - worktree_manager
  - build_orchestration
created: '2026-10-16'
last_updated: '2026-10-16'
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
  - found-at-main-merge-83db3c9ba
files_touched:
- CLAUDE.md
- docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300a-1-ia.yaml
- docs/acceptance-criteria/infrastructure/INF-500-operational-observability/INF-500d-4-iii.yaml
- docs/components.json
- scripts/build_phases_script_deploy_standalone.py
- templates/scripts/worktree_log_root.py
- templates/scripts/worktree_readiness.py
- templates/workflows-js/fast-lane-ship.js
- unit_tests/build_orchestration/_bo4400f1_routes.py
- unit_tests/build_orchestration/test_bo_4300a_1_ia.py
- unit_tests/commit_guardian/test_bp_1300e_1_iv.py
- unit_tests/portability/_inf_500d_4_iii_support.py
- unit_tests/portability/test_inf_500d_4_iii.py
- unit_tests/portability/test_inf_500d_4_iii_older_worktree_build.py
- unit_tests/portability/test_inf_500d_4_iii_reader.py
- unit_tests/workflows/_bo2400f5iii_fixtures.py
- unit_tests/workflows/test_bo2400f5iii_declined_step_core.py
- unit_tests/workflows/test_bo2400f5iii_false_positives_and_release.py
- unit_tests/workflows/test_bo2400f5iii_strong_markers_and_signals.py
out_of_scope:
- scripts/build.py
- scripts/build_deploy_manifest_helpers.py
- scripts/build_helpers.py
- scripts/build_phases.py
- scripts/build_phases_script_deploy.py
- scripts/build_phases_workflows.py
- scripts/build_shim_env.py
- scripts/build_target_guard.py
- scripts/setup_ticket_worktree.py
- scripts/worktree/check_workspace_setup_permission.py
- scripts/worktree/sweep_processes.py
- templates/scripts/commit_guardian/check_workflow_meta.py
- templates/scripts/commit_guardian/precommit_canary.py
- templates/scripts/git_recovery.py
- templates/scripts/setup_ticket_worktree.py
- templates/scripts/workspace_root.py
- templates/scripts/worktree.py
- templates/scripts/worktree_admin.py
- templates/scripts/worktree_answer.py
- templates/scripts/worktree_canaries.py
- templates/scripts/worktree_ensure_state.py
- templates/scripts/worktree_git.py
- templates/scripts/worktree_identity.py
- templates/scripts/worktree_layout.py
- templates/scripts/worktree_migrate.py
- templates/scripts/worktree_paths.py
- templates/scripts/worktree_remove.py
- templates/scripts/worktree_repo_facts.py
- templates/workflows-js/_shared/workspace-answer.js
- templates/workflows-js/build-epic.js
- templates/workflows-js/build-feature.js
- templates/workflows-js/build-ticket.js
- templates/workflows-js/finalize-feature.js
- templates/workflows-js/plan-feature.js
- templates/workflows-js/quick-fix.js
- tests/test_build_phases.py
- tests/test_git_recovery.py
- tests/test_setup_ticket_worktree.py
- tests/test_sweep_processes.py
- unit_tests/_plan_feature_e2_runner.py
- unit_tests/_plan_feature_gate_harness.py
- unit_tests/_plan_feature_harness_defaults.py
- unit_tests/_workflow_engine_defaults.py
- unit_tests/_workflow_engine_harness.py
- unit_tests/_workflow_engine_workspace.py
- unit_tests/ac_driven_dev/test_acd_2100a_2.py
- unit_tests/ac_driven_dev/test_acd_2100a_2_i.py
- unit_tests/ac_driven_dev/test_acd_2100a_2_ii.py
- unit_tests/build_orchestration/_bo2400f13_fixtures.py
- unit_tests/build_orchestration/_bo_4300a_1_fixtures.py
- unit_tests/build_orchestration/_bo_4300a_1_ia_fixtures.py
- unit_tests/build_orchestration/_bo_4300a_1_ii_fixtures.py
- unit_tests/build_orchestration/_bo_4300c_3_fixtures.py
- unit_tests/build_orchestration/_bo_4300c_6_fixtures.py
- unit_tests/build_orchestration/_bo_4300f_2_fixtures.py
- unit_tests/build_orchestration/_developer_repo_guard.py
- unit_tests/build_orchestration/_workspace_maker_build_helpers.py
- unit_tests/build_orchestration/_workspace_maker_builders.py
- unit_tests/build_orchestration/_workspace_maker_fixtures.py
- unit_tests/build_orchestration/conftest.py
- unit_tests/build_orchestration/test_bo2400f_13_occupied_workspace_refusal.py
- unit_tests/build_orchestration/test_bo2400f_13i_own_leftover_report.py
- unit_tests/build_orchestration/test_bo2400f_13ii_foreign_occupant.py
- unit_tests/build_orchestration/test_bo2400f_13iii_refusal_is_inert.py
- unit_tests/build_orchestration/test_bo2400f_13iv_free_location_proceeds.py
- unit_tests/build_orchestration/test_bo2400f_3_reconnect_stale_main_behavioral.py
- unit_tests/build_orchestration/test_bo_4100d_4.py
- unit_tests/build_orchestration/test_bo_4300_docs.py
- unit_tests/build_orchestration/test_bo_4300a_1.py
- unit_tests/build_orchestration/test_bo_4300a_1_deployed.py
- unit_tests/build_orchestration/test_bo_4300a_1_ia_lint.py
- unit_tests/build_orchestration/test_bo_4300a_1_ib.py
- unit_tests/build_orchestration/test_bo_4300a_1_ii.py
- unit_tests/build_orchestration/test_bo_4300a_2.py
- unit_tests/build_orchestration/test_bo_4300b_1.py
- unit_tests/build_orchestration/test_bo_4300b_1_i.py
- unit_tests/build_orchestration/test_bo_4300b_2.py
- unit_tests/build_orchestration/test_bo_4300b_2_i.py
- unit_tests/build_orchestration/test_bo_4300b_2_ii.py
- unit_tests/build_orchestration/test_bo_4300b_3.py
- unit_tests/build_orchestration/test_bo_4300b_3_i.py
- unit_tests/build_orchestration/test_bo_4300b_4.py
- unit_tests/build_orchestration/test_bo_4300b_5.py
- unit_tests/build_orchestration/test_bo_4300b_5_i.py
- unit_tests/build_orchestration/test_bo_4300c_1.py
- unit_tests/build_orchestration/test_bo_4300c_1_canary_git_failure.py
- unit_tests/build_orchestration/test_bo_4300c_1_canary_order.py
- unit_tests/build_orchestration/test_bo_4300c_1_i.py
- unit_tests/build_orchestration/test_bo_4300c_1_ii.py
- unit_tests/build_orchestration/test_bo_4300c_1_iii.py
- unit_tests/build_orchestration/test_bo_4300c_1_marker_and_guardian.py
- unit_tests/build_orchestration/test_bo_4300c_1_path_keyed_canaries.py
- unit_tests/build_orchestration/test_bo_4300c_1_real_install.py
- unit_tests/build_orchestration/test_bo_4300c_1_review_fixes.py
- unit_tests/build_orchestration/test_bo_4300c_2.py
- unit_tests/build_orchestration/test_bo_4300c_3.py
- unit_tests/build_orchestration/test_bo_4300c_3_i.py
- unit_tests/build_orchestration/test_bo_4300c_3_ii.py
- unit_tests/build_orchestration/test_bo_4300c_4.py
- unit_tests/build_orchestration/test_bo_4300c_4_i.py
- unit_tests/build_orchestration/test_bo_4300c_4_ii.py
- unit_tests/build_orchestration/test_bo_4300c_6.py
- unit_tests/build_orchestration/test_bo_4300c_6_real_install.py
- unit_tests/build_orchestration/test_bo_4300d_1.py
- unit_tests/build_orchestration/test_bo_4300d_1_i.py
- unit_tests/build_orchestration/test_bo_4300d_1_ii.py
- unit_tests/build_orchestration/test_bo_4300d_2.py
- unit_tests/build_orchestration/test_bo_4300d_2_i.py
- unit_tests/build_orchestration/test_bo_4300d_2_ii.py
- unit_tests/build_orchestration/test_bo_4300d_2_iii.py
- unit_tests/build_orchestration/test_bo_4300d_3.py
- unit_tests/build_orchestration/test_bo_4300d_3_i.py
- unit_tests/build_orchestration/test_bo_4300d_4.py
- unit_tests/build_orchestration/test_bo_4300e_1.py
- unit_tests/build_orchestration/test_bo_4300e_1_i.py
- unit_tests/build_orchestration/test_bo_4300e_2.py
- unit_tests/build_orchestration/test_bo_4300e_2_i.py
- unit_tests/build_orchestration/test_bo_4300e_2_ii.py
- unit_tests/build_orchestration/test_bo_4300e_3.py
- unit_tests/build_orchestration/test_bo_4300e_3_i.py
- unit_tests/build_orchestration/test_bo_4300e_4.py
- unit_tests/build_orchestration/test_bo_4300f_1.py
- unit_tests/build_orchestration/test_bo_4300f_2.py
- unit_tests/build_orchestration/test_bo_4300f_2_ia.py
- unit_tests/build_orchestration/test_bo_4300f_2_ib.py
- unit_tests/build_orchestration/test_bo_4300f_3.py
- unit_tests/build_orchestration/test_bo_4300f_3_i.py
- unit_tests/build_orchestration/test_bo_4300f_3_ii.py
- unit_tests/build_orchestration/test_bo_4300f_4.py
- unit_tests/build_orchestration/test_bo_4300f_4_i.py
- unit_tests/build_orchestration/test_bootstrap_child_stdout_to_stderr.py
- unit_tests/build_orchestration/test_fastlane_template_deploy_parity.py
- unit_tests/build_orchestration/test_fastlane_worktree_mode.py
- unit_tests/commit_guardian/test_bp_1100d_3_i_no_recipe_newly_blocked.py
- unit_tests/commit_guardian/test_check_doc_frontmatter_worktree_pathbase.py
- unit_tests/commit_guardian/test_check_workflow_meta.py
- unit_tests/feedback/test_submit_feedback_worktree_resolution.py
- unit_tests/portability/_bp900h4_layout_helpers.py
- unit_tests/portability/_deployed_check_harness.py
- unit_tests/portability/test_bp_900h_4_i.py
- unit_tests/portability/test_ge120c1i_setup_failure_reporting.py
- unit_tests/portability/test_ge_120e_1.py
- unit_tests/portability/test_ge_120e_1_i.py
- unit_tests/portability/test_ge_120e_4.py
- unit_tests/prompt_assembly/_driver_harness.py
- unit_tests/prompt_assembly/_driver_outcome_readers.py
- unit_tests/prompt_assembly/harness_build_ticket_guard.mjs
- unit_tests/prompt_assembly/test_build_feature_flatten_wiring.py
- unit_tests/prompt_assembly/test_target_resolver_worktree.py
- unit_tests/setup/test_setup_ticket_worktree.py
- unit_tests/suite_performance/test_tq_600a_9.py
- unit_tests/test_bp_300e_parse_agent_json.py
- unit_tests/test_bp_900g_6_paths.py
- unit_tests/test_build_epic_workflow.py
- unit_tests/test_build_ticket_workflow.py
- unit_tests/test_finalize_feature_preflight_branch_detection.py
- unit_tests/test_setup_ticket_worktree.py
- unit_tests/test_workflow_dual_engine.py
- unit_tests/test_workflow_variant_transform.py
- unit_tests/workflows/_bo3900_fixtures.py
- unit_tests/workflows/_bo4000_fixtures.py
- unit_tests/workflows/_inf700a5iii_scratch.py
- unit_tests/workflows/_quick_fix_harness.py
- unit_tests/workflows/_tq500f3ii_fixtures.py
- unit_tests/workflows/test_acd_2100a_1.py
- unit_tests/workflows/test_acd_2100a_3.py
- unit_tests/workflows/test_acd_2100a_4.py
- unit_tests/workflows/test_acd_2100a_5.py
- unit_tests/workflows/test_acd_2100b_1.py
- unit_tests/workflows/test_acd_2100b_2.py
- unit_tests/workflows/test_acd_2100b_3.py
- unit_tests/workflows/test_acd_2100b_3_i.py
- unit_tests/workflows/test_acd_2100b_4.py
- unit_tests/workflows/test_acd_2100b_5.py
- unit_tests/workflows/test_acd_2100b_5_i.py
- unit_tests/workflows/test_acd_2100c_1.py
- unit_tests/workflows/test_acd_2100c_2.py
- unit_tests/workflows/test_acd_2100c_3.py
- unit_tests/workflows/test_acd_2100c_3_i.py
- unit_tests/workflows/test_acd_2100c_5.py
- unit_tests/workflows/test_acd_2400_pt_store_worktree_anchor.py
- unit_tests/workflows/test_bo2000c5_phase_dispatch_reply_shape.py
- unit_tests/workflows/test_bo2400a_1_iv_test_writer_ask.py
- unit_tests/workflows/test_bo2400c1vi_bundle_layer_set.py
- unit_tests/workflows/test_bo2400c_prompt_cache_wiring.py
- unit_tests/workflows/test_bo2400f_10i_release_wiring.py
- unit_tests/workflows/test_bo2400f_10ii_release_reporting.py
- unit_tests/workflows/test_bo2400f_12_refusal_workflow.py
- unit_tests/workflows/test_bo2400f_13_workspace_refusal_workflow.py
- unit_tests/workflows/test_bo2400f_3_i_worktree_verify_workflow.py
- unit_tests/workflows/test_bo2400f_4_changelog_family.py
- unit_tests/workflows/test_bo2400f_7_iii_claim_refusal_workflow.py
- unit_tests/workflows/test_bo2400f_7_iv_claim_reply_contract_workflow.py
- unit_tests/workflows/test_bo2400f_review_and_delivery_guarantee.py
- unit_tests/workflows/test_bo2600b_lane_scope_aiming.py
- unit_tests/workflows/test_bo3900_plan_feature_cross_platform_paths.py
- unit_tests/workflows/test_bo4000_worktree_reuse_and_naming.py
- unit_tests/workflows/test_bo4000a_worktree_report_adjudication.py
- unit_tests/workflows/test_bo4000b_branch_staleness_decision.py
- unit_tests/workflows/test_bo4000c_start_location_and_occupancy.py
- unit_tests/workflows/test_bo4000d_facts_envelope_depth.py
- unit_tests/workflows/test_bo4000f_repository_reference_anchor.py
- unit_tests/workflows/test_bo_1000c_1a.py
- unit_tests/workflows/test_bo_1500a_5_i.py
- unit_tests/workflows/test_bo_1500a_5_i_dual_engine.py
- unit_tests/workflows/test_bo_1500a_5_iii.py
- unit_tests/workflows/test_bo_1500f_1.py
- unit_tests/workflows/test_bo_2300_pause_resume.py
- unit_tests/workflows/test_bo_2300a_1_ii.py
- unit_tests/workflows/test_bp600e2_divergence_behavioral.py
- unit_tests/workflows/test_bp_600d_5.py
- unit_tests/workflows/test_fast_lane_ship_structure.py
- unit_tests/workflows/test_fin_100h_refusal_not_success.py
- unit_tests/workflows/test_finalize_baseline_recovery.py
- unit_tests/workflows/test_finalize_feature_preflight.py
- unit_tests/workflows/test_finalize_pre_merge_safety_gate.py
- unit_tests/workflows/test_inf_700a_1.py
- unit_tests/workflows/test_inf_700a_1_i.py
- unit_tests/workflows/test_inf_700a_1_ii.py
- unit_tests/workflows/test_inf_700a_5_i_finalize_teardown.py
- unit_tests/workflows/test_quick_fix_escalation_and_topology.py
- unit_tests/workflows/test_quick_fix_guard_halts.py
- unit_tests/workflows/test_quick_fix_worktree_invariant.py
- unit_tests/workflows/test_tq500f3ii_gate_driver_contract.py
  - templates/scripts/worktree_readiness.py
  - templates/scripts/worktree_log_root.py
  - scripts/build_phases_script_deploy_standalone.py
  - docs/components.json
  - unit_tests/portability/test_inf_500d_4_iii_reader.py
  - unit_tests/portability/test_inf_500d_4_iii.py
  - unit_tests/portability/test_inf_500d_4_iii_older_worktree_build.py
  - unit_tests/workflows/_bo2400f5iii_fixtures.py
  - unit_tests/workflows/test_bo2400f5iii_declined_step_core.py
  - unit_tests/workflows/test_bo2400f5iii_false_positives_and_release.py
  - unit_tests/workflows/test_bo2400f5iii_strong_markers_and_signals.py
  - unit_tests/build_orchestration/_bo4400f1_routes.py
  - unit_tests/commit_guardian/test_bp_1300e_1_iv.py
  - unit_tests/build_orchestration/test_bo_4300a_1_ia.py
  - templates/workflows-js/fast-lane-ship.js
  - CLAUDE.md
  - docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300a-1-ia.yaml
agents:
  architect-review: signed_off
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  frontend-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  documentation-verifier: not_needed
  pr-reviewer: signed_off
  ac-validator: signed_off
  ac-fulfillment-gate: signed_off
  user-surface-smoker: not_needed
  commit: signed_off
  pull-request: not_needed
---

# 17: The workspace maker builds every workspace pointing at the project's durable log root, and main's tests reach the maker

## Actor / Goal
In order for logs written inside a maker-made workspace to survive its removal (INF-500d-4-iii), the maker's install build must receive the project's enduring log root, exactly as the retired bootstrap did. Main's tests that still drive the retired paths must reach the maker instead, so the epic can merge with a green suite.

## Context
- **Found:** 2026-10-16, merging origin/main into the epic (merge commit 83db3c9ba). Main's INF-500d-4-iii (commits 01bf0610a, 59ed536f8) put the log-root pass-through into `setup_ticket_worktree.py`'s `_bootstrap`. Ticket 14 (BO-4300f-2) deleted that script, so the behaviour exists nowhere on the epic branch. A maker-made workspace's build now declares its own `debugging/logs`, and those logs die with the workspace.
- **What the retired bootstrap did:**
  - It read `<main>/.leafcutter/config/knowledge_sink.json` and used `operational_log_root`, or `Path(knowledge_emission_sink).parent` for an older declaration. The root was never derived from the repository path.
  - When the file was absent, unreadable, keyless or held a relative root, it printed `WARNING: no enduring log root readable from <path> (<why>); logs written in this worktree will not survive its removal.` and passed `--no-log-root`. Otherwise it passed `--log-root <root>`.
  - It ran `build.py --target-dir <worktree> [flag]` with stderr captured. If the workspace's own `build.py` predated the flags (exit 2 with `unrecognized arguments`), it retried once without the flag and warned.
- **Where the maker builds:** `templates/scripts/worktree_readiness.py` → `run_install_build()` runs `[python, <ws>/scripts/build.py, --target-dir, ws, --config-path, cfg]` with `LEAFCUTTER_SHIM_STRATEGY=copy`. It passes neither flag and takes no project-install path, so the caller must supply it. Architect-review decides where the project's install is read from in each layout, including the package repository (which holds no install after Q6).
- **Tests main added that reach the retired paths:**
  - `unit_tests/portability/test_inf_500d_4_iii.py` and `test_inf_500d_4_iii_older_worktree_build.py` call the deleted script's `_bootstrap`.
  - BO-2400f-5-iii fixtures and tests (`unit_tests/workflows/_bo2400f5iii_fixtures.py`, `test_bo2400f5iii_*.py`) and `unit_tests/build_orchestration/_bo4400f1_routes.py` script the old fast-lane `worktree-agent` / `fastlane-worktree(-verify)` steps and the old `resolve-connected` reply shape.
  - `unit_tests/commit_guardian/test_bp_1300e_1_iv.py:29,31` spells `git worktree add` directly, a hit for the BO-4300f-2 census.
- The merge re-applied main's BO-2400f-5-iii decline classification on the maker-based resolve step in `fast-lane-ship.js`. Tests must prove that path, not the old shape.

## Acceptance Criteria
- [x] AC-1: A workspace the deployed maker makes has a `config/knowledge_sink.json` whose `operational_log_root` is the project's enduring root. Its feedback, telemetry and knowledge sinks sit directly under that root (INF-500d-4-iii).
- [x] AC-2: When the project's root cannot be read, the maker's answer stays ok. The build records the empty declaration (`--no-log-root`), and the warning names the path tried and why.
- [x] AC-3: A workspace whose own `build.py` predates the flags is still built: one retry without the flag, plus a warning.
- [x] AC-4: The INF-500d-4-iii proofs run the deployed maker as a separate process, not the deleted script. The BO-2400f-5-iii and BO-4400f-1 tests drive the maker-based fast-lane steps. `test_bp_1300e_1_iv.py` makes its linked checkout through the exempt `link_checkout` helper. The BO-4300f-2 census stays empty.

## Test Requirements

```yaml
tests:
- name: test_maker_workspace_inherits_the_projects_durable_log_root
  file: unit_tests/portability/test_inf_500d_4_iii.py
  covers:
  - INF-500d-4-iii
  asserts: The deployed maker's ok answer names a workspace whose knowledge_sink.json records the project's operational_log_root (absolute) and every sink directly under it.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_unreadable_project_root_builds_with_no_log_root_and_warns
  file: unit_tests/portability/test_inf_500d_4_iii.py
  covers:
  - INF-500d-4-iii
  asserts: With the project's knowledge_sink.json absent or relative, the maker still answers ok, the workspace records {} and the warning names the path and reason.
  framework: unittest
  type: behavioral
  angle: failure
- name: test_older_workspace_build_is_retried_without_the_flag
  file: unit_tests/portability/test_inf_500d_4_iii_older_worktree_build.py
  covers:
  - INF-500d-4-iii
  asserts: A fixture build that rejects --log-root with exit 2 is retried once without it; the workspace is built and a warning is printed.
  framework: unittest
  type: behavioral
  angle: failure
```

## Implementation Notes
- Use the BO-4300f-4 fixture module (`_workspace_maker_fixtures.py`) for deployed-maker runs and real temporary hubs. Never mock git, and never spawn the package's own `build.py` (CLAUDE.md "Tests must not spawn their own build.py"). Fixture projects carry the stub build entry point.
- Do not re-create any former way: no `git worktree add/remove` outside the exemptions, and no own repository search.
- `worktree_readiness.py` is near its size limit. Keep any helper small, or put it in its own module.

## Agent Contracts

### python-coder
- [x] AC-1, AC-2, AC-3 in `templates/scripts/worktree_readiness.py` (and the maker's call site).

### test-writer
- [ ] AC-4 test migrations and the three tests above (red first).

## Architecture Notes

Impact: small-to-medium, no always-large trigger (no migration, hypertable, FastAPI or ADR-contract change). Components: worktree_manager and build_orchestration (the new module and the deploy list entry). Escalation: none.

1. **Where the root is read from: the install that deployed the running maker.** `install_root = Path(__file__).resolve().parents[1]` of the deployed `scripts/worktree_*.py` (the same two-directories-up arithmetic as `sink_resolution.deployed_output_root`). The maker reads `<install_root>/config/knowledge_sink.json`. This covers every layout with one rule and no project-path derivation (ADR-069 section 3: never derive the root from a repository path):
   - Adopter project, clone-based workspace: the maker run is the project's install, so `<project>/.leafcutter/config/knowledge_sink.json`. The clone does not carry it (`.leafcutter` is gitignored), so the project's install is the only source.
   - Package repository after Q6: the maker run is the parent workspace's install (`C:/Users/Hendrik/Code/leafcutter/.leafcutter`), which is where the root was recorded. Do not look inside `leafcutter-ai/`.
   - A maker run from inside a workspace reads that workspace's own declaration, which already inherited the root, so the root passes down transitively.
   - Replaces `main_repo`: `main_repo` is not needed. Neither `project_root` (wrong in the package layout, as ADR-069 section 3 already warns) nor a build-recorded config is used.
   - Do not call `sink_resolution --print-location root`: it refuses a legacy two-key declaration (it requires `operational_log_root`), and the parent install here is exactly that (verified: it holds only `knowledge_emission_sink` and `operational_telemetry_stream`). The retired bootstrap accepted `Path(knowledge_emission_sink).parent` for it, ADR-069 section 3 still requires that, and AC-1 would otherwise warn on this repository's own workspaces. `worktree_readiness.py` is stdlib-only and standalone, so it also cannot import `scripts/knowledge/`.
   - Do not parse in `worktree_readiness.py`. Put a reader in a new stdlib-only module `templates/scripts/worktree_log_root.py` exposing `inherited_log_root_args(install_root) -> tuple[list[str], str | None]` (flag list plus warning text). Rules: `operational_log_root`, else parent of `knowledge_emission_sink`; absolute required; typed excepts (`OSError`, `ValueError`, `KeyError`, `TypeError`, `AttributeError`); the warning keeps the retired wording (`WARNING: no enduring log root readable from <path> (<why>); logs written in this workspace will not survive its removal.`); the fallback flag is `--no-log-root`.
   - Deploy: add `"worktree_log_root.py"` to `NAMED_STANDALONE_SCRIPTS` in `scripts/build_phases_script_deploy_standalone.py` (beside `worktree_canaries.py`), register it in `docs/components.json` with the other maker modules, and extend the doc string/decision history in `build_deploy_manifest_helpers.py` only if the parity test demands it. A tracked-output resync is not needed (no `scripts/` copy of the maker exists after the BO-4300f-2 deletion).

2. **Call-site shape.** `run_install_build(workspace, config_path)` keeps its signature (callers and `prove_ready` unchanged; no new parameter threaded through `worktree.py`). Inside it: `flags, warning = wlr.inherited_log_root_args(Path(__file__).resolve().parents[1])`; print the warning to stderr (never stdout, the answer channel); loop `for extra in (flags, [])` around the existing `subprocess.run`; retry once without the flag when the exit is 2 and `unrecognized arguments` is in stderr, with a second warning (retired wording). To stay under the ratchet, factor the loop into a helper in `worktree_log_root.py` (`run_with_inherited_log_root(cmd, flags, **run_kwargs)` returning the last `CompletedProcess`) so `worktree_readiness.py` changes by at most a few lines: one import, one call, no new logic. Measured length now: 276 lines, and the ratchet blocks growth of any file past its limit, so the net growth in `worktree_readiness.py` must be zero or negative after the edit. Run `check_file_size.py` before handing over. The `LEAFCUTTER_SHIM_STRATEGY=copy` env, the `forward_child_output` call and the excerpt logic stay as they are.

3. **Test migrations.** The ticket's list is enough, with these additions:
   - Add one small pure-unit module `unit_tests/portability/test_inf_500d_4_iii_reader.py` for the reader (absolute root, legacy two-key, relative, keyless, absent, directory) so the warning-reason wording is pinned without a subprocess. It is in files_touched now.
   - Fixture projects need a `config/knowledge_sink.json` in the install output root that holds the deployed maker. Build it in `_workspace_maker_fixtures.py` if it does not already, rather than in each test.
   - The three required tests stay the contract. The stub build entry point in the fixture must record its argv (the older-build test needs exit 2 plus `unrecognized arguments` on the first call only).
   - BO-2400f-5-iii and BO-4400f-1 only need the step names and the maker's `ok` answer shape; reuse the existing fast-lane maker fixtures, add nothing new.
   - `test_bp_1300e_1_iv.py` uses `link_checkout`; no extra work.

4. **ADR.** No new ADR and no ADR-018 amendment. ADR-069 section 3 states the rule (read the recorded declaration, never derive from a path, `operational_log_root` else parent of the emission sink, loud warning) but names a retired mechanism (`setup_ticket_worktree.py`, `main_repo`). Fix this with a one-paragraph implementation-record note appended to ADR-069 (status unchanged, no decision change): "the workspace maker now does this, reading the declaration of the install that deployed it". Do it in the documentation pass or leave it to the epic's closing ADR sweep; the ticket keeps `documentation-expert: not_needed` and `requires_adr: false`. ADR-018 needs nothing: Amendment 1 already makes the maker the single install builder.

Acceptance adjustments: none to the AC text. AC-2's warning must name the declaration path tried (`<install_root>/config/knowledge_sink.json`) and the reason. Stderr only.

## Sign-offs
- [x] architect-review — 2026-10-16 12:00
- [x] test-writer — 2026-10-16 19:09
- [x] python-coder — 2026-10-16 20:30
- [x] test-runner — 2026-10-16 22:07
- [x] pr-reviewer — 2026-10-16 23:00
- [x] ac-validator — 2026-10-16 23:30
- [x] ac-fulfillment-gate — 2026-10-16 23:45
- [x] commit — 2026-10-17 22:29

## Comments

_(Append-only log — leave blank when authoring.)_

### 2026-10-16 12:00 — architect-review (status: ok)
feedback-id: fb_2026-10-16_192e068b
Decisions are in Architecture Notes. The feedback id was submitted via the parent install (the source-tree submit_feedback.py found no config/knowledge_sink.json).

### 2026-10-16 19:09 — test-writer (status: ok)
feedback-id: fb_2026-10-16_d7b23fc2

(classification: test_drift) for every migrated main test: production (the maker, fast-lane-ship.js) is correct; the tests still drove the retired setup_ticket_worktree.py bootstrap, the old fastlane-worktree / fastlane-worktree-verify steps and the old resolve-connected reply shape. No production file was touched.

## Test Writer — Completion Report

### Tests Written / migrated
| File | Directory | Framework | Status |
|---|---|---|---|
| test_inf_500d_4_iii_reader.py (new, 12 tests, 223 lines) | unit_tests/portability/ | pytest, pure unit | written, red (absence) |
| _inf_500d_4_iii_support.py (new, 157 lines, not collected) | unit_tests/portability/ | support | written |
| test_inf_500d_4_iii.py (341 lines, was 390) | unit_tests/portability/ | pytest | maker tests red; build-level tests unchanged and green |
| test_inf_500d_4_iii_older_worktree_build.py | unit_tests/portability/ | pytest | re-pointed at the deployed maker, red |
| _bo2400f5iii_fixtures.py, test_bo2400f5iii_declined_step_core.py, _false_positives_and_release.py, _strong_markers_and_signals.py | unit_tests/workflows/ | unittest | migrated, green |
| _bo4400f1_routes.py | unit_tests/build_orchestration/ | support | migrated, fast-lane route verified by a direct run |
| test_bp_1300e_1_iv.py | unit_tests/commit_guardian/ | pytest | _worktree() now uses link_checkout |

### Verification Run
- Command: AC_ENFORCE_STRICT=1 PYTHONUTF8=1 python -m pytest unit_tests/portability/test_inf_500d_4_iii_older_worktree_build.py unit_tests/portability/test_inf_500d_4_iii_reader.py unit_tests/portability/test_inf_500d_4_iii.py -q
- Result: 20 failed (expected red), 8 passed (the build-level tests main already had: declaration shape, plain build, --log-root verbatim/relative refusal, location-query refusal, 4 sink-parity cases).
- Migrated: unit_tests/workflows/test_bo2400f5iii_*.py 28 passed. `python -m unit_tests.build_orchestration.test_bo_4300f_2 --census` prints nothing (exit 0; before the migration it printed test_bp_1300e_1_iv.py:29 and :31).
- Not runnable on this Windows host: test_bo_4400f_1.py and test_bp_1300e_1_iv.py error in the shared-layout fixture (SharedReferenceLayoutError: requires POSIX fcntl.flock), a local-only limit unrelated to this ticket. _bo4400f1_routes.run_route for fast-lane-ship.js was driven directly: it dispatches workspace-ensure, resolve-connected, ..., fastlane-pr and ends status ok. test_bp_1300e_1_iv.py and the routes file compile.
- Expected red until python-coder lands: everything in the red_baseline below. Expected green now: all 28 BO-2400f-5-iii tests and the 8 passing build-level portability tests.
- File size (check_file_size.py, all staged files): pass. New files 223 and 157 lines; test_inf_500d_4_iii.py shrank from 390 to 341.

### Notes on the migrations
- BO-2400f-5-iii: the lane now starts with workspace-ensure (shell-runner reply carrying the maker's ok answer) and resolve-connected (command-step-runner reply with exit_status and stdout holding the JSON id list), built with the existing workspace_ensure_from_opened / resolve_connected_reply helpers. The decline classification on the resolve step is still proven (the strong-marker case now expects agent command-step-runner; a plain-string decline halts as declined_step with target = the confirmed workspace). A command-step reply with a non-zero exit_status and "refused" in its stderr is still the step's own result and ends status error / failing_phase resolve (the old "empty ac_ids plus refusal word" promise). workspace-ensure is excluded from the declined_step sweep (its failure is the shared workspaceFailure error, per BO-4300c-3); a new test pins that a declined workspace step ends the run as status error quoting the reply, with no later dispatch and no release.
- INF-500d-4-iii promises kept: inherited root R recorded and never derived from a repository path (test 1); unreadable root warns naming the path and never leaves the workspace's own root (test 2); older-build retry plus its control (older file); legacy two-key root (new); config/guard/log roots resolve in one workspace and the location query is side-effect free (now run against verbatim deployed consumer files copied into the maker-made workspace, a real maker-output to consumer seam); parity check (now against the shared deployed layout, no workspace needed).
- The fixture project's scripts/build.py is the shared stub plus argv recording (BUILD_STUB_LOG) and, when asked, exit 2 "unrecognized arguments" on the first call that carries a log-root flag. It writes the declaration the flags ask for ({} for --no-log-root). The package's own build.py is never spawned by the new tests (the shared deployed layout is built once by ensure_deployed_layout, as before).
- The deployed-maker proofs run a private copy of the deployed maker inside its own install (project_install), so <install>/config/knowledge_sink.json can be varied per case; siblings come from the shared deployed layout.

### Three Questions (per guarding test)
| Test | Q1 smallest wrong change | Q2 can it fail? | Q3 control row | Label |
|---|---|---|---|---|
| test_maker_workspace_inherits_the_projects_durable_log_root | derive the root from the project path or leave the build default; pass the flag but not R verbatim | observed red today: workspace records <ws>/debugging/logs; asserts exact == R, one build call, startswith checks against workspace and project | legacy and older-build tests use other declarations | observed |
| test_unreadable_project_root_builds_with_no_log_root_and_warns | refuse instead of ok; pass nothing instead of --no-log-root; warn on stdout or without the path | observed red: workspace records the default declaration, no warning; asserts {}, exactly one call with --no-log-root and no --log-root, warning regex with the exact path | the happy-path test (readable declaration) | observed |
| test_older_workspace_build_is_retried_without_the_flag | retry with the flag again; retry on any failure; never retry | observed red (one call); asserts exactly 2 calls, the second without any flag, a WARNING naming the rejected flag | test_a_workspace_build_that_knows_the_flag_is_called_once_with_the_recorded_root (exactly 1 call, no warning) | observed |
| reader tests | operational_log_root ignored in favour of the sink parent; relative root passed through; raise instead of warn | reasoned, plus observed green against a scratch reference implementation (not committed); red today only by absence | full vs legacy vs unreadable shapes | reasoned |
| test_exit_2_for_another_reason_or_without_flags_is_not_retried | retry on any exit 2, with no flags, or on exit 1 with the marker | reasoned | the retry test above | reasoned |

Vacuity checklist: exact count (calls == 1 / == 2, == {}, == R) done; control row done for the retry (accepting build) and the reader (full vs legacy vs unreadable); distinct new inputs: R is distinct from the project, workspace and the build default; collaborator call-count: the stub build's recorded argv list.
Wrong versions the tests now catch: root derived from the project path; build default left in place; --log-root dropped; refusing on an unreadable root; warning on stdout; retry with the same flag; unconditional retry; relative root accepted.
Scratch-checked: the three deployed scenarios (full, absent, older) go green against a copy of the maker patched in the scratchpad with a scratch reference worktree_log_root.py (never committed).

### Notes
- The three tests named in Test Requirements are framework: unittest; they are written as pytest functions to share the file's module-scope maker fixture (collected and run the same way).
- test_inf_500d_4_iii_reader.py imports worktree_log_root lazily inside each test, so each test fails individually (absence red) instead of one collection error. It pins inherited_log_root_args(install_root) -> (flags, warning) and run_with_inherited_log_root(cmd, flags, **run_kwargs) exactly as architect-review specified.

red_baseline:
  - test_name: test_maker_workspace_inherits_the_projects_durable_log_root
    file: unit_tests/portability/test_inf_500d_4_iii.py
    kind: assertion
    error: "AssertionError: assert '...proj\\project-worktrees\\feature\\inherit\\debugging\\logs' == '...inf500d4iii_inherit0\\enduring\\logs'"
  - test_name: test_unreadable_project_root_builds_with_no_log_root_and_warns
    file: unit_tests/portability/test_inf_500d_4_iii.py
    kind: assertion
    error: "AssertionError: [absent] workspace must record the empty declaration: {'operational_log_root': '...\\debugging\\logs', ...}"
  - test_name: test_legacy_two_key_declaration_is_inherited_from_the_parent_of_the_emission_sink
    file: unit_tests/portability/test_inf_500d_4_iii.py
    kind: assertion
    error: "AssertionError: assert '...\\feature\\legacy\\debugging\\logs' == '...\\enduring\\logs'"
  - test_name: test_config_and_guard_roots_still_resolve_to_the_worktree
    file: unit_tests/portability/test_inf_500d_4_iii.py
    kind: assertion
    error: "AssertionError: assert '...\\feature\\inherit\\debugging\\logs' == '...\\enduring\\logs'"
  - test_name: test_location_query_reports_each_stream_and_creates_nothing
    file: unit_tests/portability/test_inf_500d_4_iii.py
    kind: assertion
    error: "AssertionError: root: got '...\\project-worktrees\\feature\\inherit\\debugging\\logs' want '...\\inf500d4iii_inherit0\\enduring\\logs'"
  - test_name: test_older_workspace_build_is_retried_without_the_flag[project_has_a_declaration]
    file: unit_tests/portability/test_inf_500d_4_iii_older_worktree_build.py
    kind: assertion
    error: "AssertionError: the maker must retry a build that rejected the flag exactly once; saw [['--target-dir', '...']]"
  - test_name: test_older_workspace_build_is_retried_without_the_flag[project_has_none]
    file: unit_tests/portability/test_inf_500d_4_iii_older_worktree_build.py
    kind: assertion
    error: "AssertionError: the maker must retry a build that rejected the flag exactly once; saw [['--target-dir', '...']]"
  - test_name: test_a_workspace_build_that_knows_the_flag_is_called_once_with_the_recorded_root
    file: unit_tests/portability/test_inf_500d_4_iii_older_worktree_build.py
    kind: assertion
    error: "AssertionError: the build must be told the recorded root: ['--target-dir', '...']"
  - test_name: test_absolute_root_is_passed_verbatim_and_nothing_is_warned
    file: unit_tests/portability/test_inf_500d_4_iii_reader.py
    kind: absence
    error: "ModuleNotFoundError: No module named 'worktree_log_root'"
  - test_name: test_operational_log_root_wins_over_the_emission_sink_parent
    file: unit_tests/portability/test_inf_500d_4_iii_reader.py
    kind: absence
    error: "ModuleNotFoundError: No module named 'worktree_log_root'"
  - test_name: test_legacy_declaration_gives_the_parent_of_the_emission_sink
    file: unit_tests/portability/test_inf_500d_4_iii_reader.py
    kind: absence
    error: "ModuleNotFoundError: No module named 'worktree_log_root'"
  - test_name: test_relative_root_is_refused_with_the_reason_named
    file: unit_tests/portability/test_inf_500d_4_iii_reader.py
    kind: absence
    error: "ModuleNotFoundError: No module named 'worktree_log_root'"
  - test_name: test_relative_legacy_sink_is_refused
    file: unit_tests/portability/test_inf_500d_4_iii_reader.py
    kind: absence
    error: "ModuleNotFoundError: No module named 'worktree_log_root'"
  - test_name: test_declaration_with_neither_key_names_the_missing_key
    file: unit_tests/portability/test_inf_500d_4_iii_reader.py
    kind: absence
    error: "ModuleNotFoundError: No module named 'worktree_log_root'"
  - test_name: test_absent_declaration_is_warned_with_the_path_tried
    file: unit_tests/portability/test_inf_500d_4_iii_reader.py
    kind: absence
    error: "ModuleNotFoundError: No module named 'worktree_log_root'"
  - test_name: test_a_directory_in_place_of_the_declaration_is_warned
    file: unit_tests/portability/test_inf_500d_4_iii_reader.py
    kind: absence
    error: "ModuleNotFoundError: No module named 'worktree_log_root'"
  - test_name: test_unparseable_and_non_object_declarations_are_warned
    file: unit_tests/portability/test_inf_500d_4_iii_reader.py
    kind: absence
    error: "ModuleNotFoundError: No module named 'worktree_log_root'"
  - test_name: test_a_build_that_rejects_the_flag_is_retried_once_without_it_and_warned
    file: unit_tests/portability/test_inf_500d_4_iii_reader.py
    kind: absence
    error: "ModuleNotFoundError: No module named 'worktree_log_root'"
  - test_name: test_a_build_that_accepts_the_flag_runs_once_without_a_warning
    file: unit_tests/portability/test_inf_500d_4_iii_reader.py
    kind: absence
    error: "ModuleNotFoundError: No module named 'worktree_log_root'"
  - test_name: test_exit_2_for_another_reason_or_without_flags_is_not_retried
    file: unit_tests/portability/test_inf_500d_4_iii_reader.py
    kind: absence
    error: "ModuleNotFoundError: No module named 'worktree_log_root'"

completion_manifest:
  cross_layer_seam_answer:
    result: covered
    producing_side: "the deployed maker's install build step (worktree_readiness.run_install_build reading the project install's config/knowledge_sink.json)"
    consuming_side: "the maker-made workspace's own build.py (argv and recorded declaration) and, downstream, the deployed sink_resolution --print-location query run against that workspace's declaration"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "python <install>/scripts/worktree.py ensure --kind feature --slug <slug> (the deployed maker as a separate process, via run_maker)"

### 2026-10-16 20:30 — python-coder (status: ok)
feedback-id: fb_2026-10-16_e82f6734

New stdlib-only `templates/scripts/worktree_log_root.py` (inherited_log_root_args, run_with_inherited_log_root, build_with_inherited_log_root); `worktree_readiness.run_install_build` calls it with `Path(__file__).resolve().parents[1]` (file net 0 lines, 276 -> 276 incl. history entry). Registered in NAMED_STANDALONE_SCRIPTS and docs/components.json.

red_baseline_results:
  - test_name: test_maker_workspace_inherits_the_projects_durable_log_root
    result: green
  - test_name: test_unreadable_project_root_builds_with_no_log_root_and_warns
    result: green
  - test_name: test_legacy_two_key_declaration_is_inherited_from_the_parent_of_the_emission_sink
    result: green
  - test_name: test_config_and_guard_roots_still_resolve_to_the_worktree
    result: green
  - test_name: test_location_query_reports_each_stream_and_creates_nothing
    result: green
  - test_name: test_older_workspace_build_is_retried_without_the_flag (2 params)
    result: green
  - test_name: test_a_workspace_build_that_knows_the_flag_is_called_once_with_the_recorded_root
    result: green
  - test_name: 12 reader tests in test_inf_500d_4_iii_reader.py
    result: green

All 28 tests in the three portability files pass. Two failures in test_bo_4300a_1_ia / test_bo_4300f_2_ia also fail at HEAD (pre-existing).

### 2026-10-16 21:00 — test-writer (status: ok)
feedback-id: fb_2026-10-16_3eda0d91

Re-dispatch after kernel decision dec-53b45488fdc621d9: done AC BO-4300a-1-ia's last clause was amended (amended_by entry, staged). A refused shell step now ends the workflow with an error quoting the answer, OR, where a more specific rule classifies the refusal (BO-2400f-5-iii declined step in the fast lane), with that rule's halt, which also quotes it. Updated unit_tests/build_orchestration/test_bo_4300a_1_ia.py::test_refused_non_workspace_shell_step_ends_the_workflow_with_a_quoting_error: fast-lane-ship.js resolve-connected accepts status 'error' OR status 'halt' with classification 'halt' and halt_kind 'declined_step' (per buildDeclinedStepHalt); plan-feature.js stays 'error'. The TOKEN quote check and the no-later-dispatch check are unchanged for every case. Classification: (classification: consumer_drift) - spec amended, test follows. Files_touched extended for the coder fix and the AC/CLAUDE.md amendment.

red_baseline:
  - test_name: test_refused_non_workspace_shell_step_ends_the_workflow_with_a_quoting_error
    file: unit_tests/build_orchestration/test_bo_4300a_1_ia.py
    kind: assertion
    error: "AssertionError: fast-lane-ship.js/no_result: terminal payload does not quote the reply (only failure; 1 failed, 5 passed)"

### 2026-10-16 22:00 — python-coder (status: ok)
feedback-id: fb_2026-10-16_188c08d6

Fast-lane classifyStepReply: the command-step no-exit_status fallback now quotes the raw reply (JSON), so the declined-step halt carries it. One redundant comment line removed (file 1642 -> 1641, ratchet OK). CLAUDE.md log-root passage now points to the workspace maker and docs/how-to/get-a-workspace.md. red_baseline_results: test_refused_non_workspace_shell_step_ends_the_workflow_with_a_quoting_error: green. 39 tests pass (AC_ENFORCE_STRICT=1).

### 2026-10-16 23:00 — pr-reviewer (status: ok)
feedback-id: fb_2026-10-16_cec6f1ae

No high-confidence findings. Reader/retry module verified (declaration of the deploying install, legacy fallback, absolute-only, stderr-only warnings, single retry on exit 2 + "unrecognized arguments", typed excepts, deployed + registered). Test migrations keep every assertion; AC amendment matches test_bo_4300a_1_ia.py. Low notes: JSON.stringify(reply) in fast-lane-ship.js is unbounded in size; a redundant comment line was removed for the file-size ratchet.

### 2026-10-16 22:07 — test-runner (status: ok)
feedback-id: fb_2026-10-16_2dc2ff82

Ran 192 test files (ticket files_touched, test_bo_43*, workflow tests loading the five ship/build/plan JS files) with AC_ENFORCE_STRICT=1: 153 failed, 1090 passed, 1 skipped, 8 errors, 473 subtests passed. Every failure also fails at HEAD (bc100fab8 without the staged changes) in a scratch worktree (111 unique ids vs 112; the one id differing, test_tq600a_13_xx_only_the_exact_check_name_is_the_hold, shows as FAILED subtests at baseline and ERROR here, same 11 failures on a standalone rerun in both trees). New failures: 0. Failures are the known Windows-local set (acd_2100*, bo_100e, bo_3000/3800, tq_600a_13, bp_1300e_1_iv, etc.).

completion_manifest:
  test_suite_executed: true
  all_tests_passing:
    result: false
    reason: 153 failures, all identical to the HEAD baseline on this Windows host (none introduced by ticket 17)
    remediation: none for ticket 17; trust CI for the host-local set
  failure_report_structured: true

### 2026-10-16 23:30 — ac-validator (status: ok)
feedback-id: fb_2026-10-16_bd72baea

All 4 ACs covered. Tests: AC_ENFORCE_STRICT=1 PYTHONUTF8=1 pytest of 3 portability files, test_bo_4300a_1_ia.py, 3 test_bo2400f5iii files = 52 passed; BO-4300f-2 census prints nothing (exit 0).
AC-1 covered: impl templates/scripts/worktree_log_root.py inherited_log_root_args + worktree_readiness.py run_install_build (build_with_inherited_log_root); test test_maker_workspace_inherits_the_projects_durable_log_root (unit_tests/portability/test_inf_500d_4_iii.py)
AC-2 covered: impl worktree_log_root.py inherited_log_root_args (--no-log-root + stderr warning naming path and reason); test test_unreadable_project_root_builds_with_no_log_root_and_warns (test_inf_500d_4_iii.py), reader tests (test_inf_500d_4_iii_reader.py)
AC-3 covered: impl worktree_log_root.py run_with_inherited_log_root (one retry on exit 2 + unrecognized arguments, warning); test test_older_workspace_build_is_retried_without_the_flag (test_inf_500d_4_iii_older_worktree_build.py)
AC-4 covered: impl/migration _bo2400f5iii_fixtures.py, _bo4400f1_routes.py, test_bp_1300e_1_iv.py _worktree() via link_checkout; tests test_bo2400f5iii_* (28 green), census empty. test_bp_1300e_1_iv.py/test_bo_4400f_1.py not runnable on Windows (fcntl); compile verified, intent read.
INF-500d-4-iii covered by the above (deployed in NAMED_STANDALONE_SCRIPTS + docs/components.json).
BO-4300a-1-ia amendment: YAML last clause and amended_by entry staged; test_refused_non_workspace_shell_step_ends_the_workflow_with_a_quoting_error passes (fast-lane-ship.js classifyStepReply now quotes the raw reply).

### 2026-10-16 23:45 — ac-fulfillment-gate (status: ok)
feedback-id: fb_2026-10-16_37e38c66

All 1 AC verified (INF-500d-4-iii, L3, work_status done). Auto-fixes: implemented_by repointed from the deleted templates/scripts/setup_ticket_worktree.py and scripts/setup_ticket_worktree.py to templates/scripts/worktree_log_root.py and templates/scripts/worktree_readiness.py (all listed paths exist); covered_by gained unit_tests/portability/test_inf_500d_4_iii_reader.py (existing harvest test still exists and was kept). check_ac_schema.py exit 0; check_done_proof.py exit 0. BO-4300a-1-ia YAML left as staged.

### 2026-10-17 22:22 — python-coder (status: ok)
feedback-id: fb_2026-10-16_394abea5

check-exception-handling IO-001 fix in templates/scripts/worktree_log_root.py: both build subprocess.run calls now go through _run_build, which catches (OSError, subprocess.SubprocessError) and re-raises subprocess.SubprocessError with context. Caller worktree_readiness.run_install_build handler unchanged (BOOTSTRAP_FAILED refusal path identical).

### 2026-10-17 22:29 — commit (status: ok)
feedback-id: fb_2026-10-16_e35eb5ad

Committed in two parts. Part 1 (tests) = f8e491eb8; part 2 (implementation, AC YAMLs, docs, CLAUDE.md, ticket) = ad0ff5fab. All pre-commit hooks passed on the first attempt; no overrides used.
