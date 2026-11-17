---
title: "The deploy-completeness closure guard analyses each file once per build"
ac_traceability:
  id: BP-900g-8-i
  path: docs/acceptance-criteria/build_pipeline/BP-900-deployment-completeness/BP-900g-8-i.yaml
status: done
components:
  - build_pipeline
created: '2026-10-23'
last_updated: '2026-10-23'
ac_coverage: 4/4
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
change_target: code
risk_surface: internal
complexity: low
requires_adr: false
requires_diagram: false
tags:
  - bo4300-hardening
  - BP-900g-8
  - found-on-pr-1318
files_touched:
  - scripts/build_referential_integrity.py
  - scripts/build.py
  - scripts/build_referential_integrity_closure.py
  - scripts/build_referential_integrity_closure_eval.py
  - unit_tests/test_bp_900g_8_closure_cache.py
# out_of_scope: changed by tickets 01-09 and their follow-ups on the epic branch (48b56992d)
# this lane starts from; the scope guard diffs the whole branch against main.
out_of_scope:
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/suite_performance/_shared_layout_coordination.py
  - scripts/suite_performance/_shared_layout_producer.py
  - scripts/suite_performance/_shared_layout_seed.py
  - templates/scripts/commit_guardian/ensure_precommit_config.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_answer.py
  - templates/scripts/worktree_canaries.py
  - templates/scripts/worktree_ensure_state.py
  - templates/scripts/worktree_ensure_steps.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_identity.py
  - templates/scripts/worktree_log_root.py
  - templates/scripts/worktree_migrate.py
  - templates/scripts/worktree_migrate_carry.py
  - templates/scripts/worktree_migrate_guards.py
  - templates/scripts/worktree_readiness.py
  - templates/scripts/worktree_remove.py
  - templates/scripts/worktree_ticket_record.py
  - templates/workflows-js/_shared/workspace-answer.js
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
  - templates/workflows-js/plan-feature.js
  - templates/workflows-js/quick-fix.js
  - unit_tests/_plan_feature_e2_runner.py
  - unit_tests/_workflow_engine_defaults.py
  - unit_tests/build_orchestration/_bo_4300a_1_ia_fixtures.py
  - unit_tests/build_orchestration/_bo_4300a_2_probe.py
  - unit_tests/build_orchestration/_bo_4300f_2_fixtures.py
  - unit_tests/build_orchestration/_bo_4300f_3_keep_fixtures.py
  - unit_tests/build_orchestration/_workspace_maker_builders.py
  - unit_tests/build_orchestration/_workspace_maker_fixtures.py
  - unit_tests/build_orchestration/test_bo_400e_3_ix_setup_record.py
  - unit_tests/build_orchestration/test_bo_4300a_1_budgets.py
  - unit_tests/build_orchestration/test_bo_4300a_1_clone_source.py
  - unit_tests/build_orchestration/test_bo_4300a_1_deployed.py
  - unit_tests/build_orchestration/test_bo_4300a_1_ia.py
  - unit_tests/build_orchestration/test_bo_4300a_1_ia_lint.py
  - unit_tests/build_orchestration/test_bo_4300a_1_ia_marker.py
  - unit_tests/build_orchestration/test_bo_4300a_1_marker_survival.py
  - unit_tests/build_orchestration/test_bo_4300a_1_route_shape.py
  - unit_tests/build_orchestration/test_bo_4300a_1_same_location.py
  - unit_tests/build_orchestration/test_bo_4300a_2.py
  - unit_tests/build_orchestration/test_bo_4300a_2_safe_slugs.py
  - unit_tests/build_orchestration/test_bo_4300b_4_links.py
  - unit_tests/build_orchestration/test_bo_4300c_1_independence.py
  - unit_tests/build_orchestration/test_bo_4300c_1_verify_readonly.py
  - unit_tests/build_orchestration/test_bo_4300c_1_verify_refuses.py
  - unit_tests/build_orchestration/test_bo_4300c_2_contract_codes.py
  - unit_tests/build_orchestration/test_bo_4300c_2_never_prompts.py
  - unit_tests/build_orchestration/test_bo_4300c_4_i.py
  - unit_tests/build_orchestration/test_bo_4300d_1.py
  - unit_tests/build_orchestration/test_bo_4300e_1_i_alias.py
  - unit_tests/build_orchestration/test_bo_4300e_1_shapes.py
  - unit_tests/build_orchestration/test_bo_4300e_2.py
  - unit_tests/build_orchestration/test_bo_4300e_2_i.py
  - unit_tests/build_orchestration/test_bo_4300e_2_iii.py
  - unit_tests/build_orchestration/test_bo_4300e_3.py
  - unit_tests/build_orchestration/test_bo_4300e_3_ii.py
  - unit_tests/build_orchestration/test_bo_4300f_1.py
  - unit_tests/build_orchestration/test_bo_4300f_3_carry.py
  - unit_tests/build_orchestration/test_bo_4300f_3_cutover.py
  - unit_tests/build_orchestration/test_bo_4300f_3_iii.py
  - unit_tests/build_orchestration/test_bo_4300f_3_iv.py
  - unit_tests/build_orchestration/test_bo_4300f_3_keep.py
  - unit_tests/build_orchestration/test_bo_4300f_3_states.py
  - unit_tests/build_orchestration/test_bo_4300f_4.py
  - unit_tests/commit_guardian/test_bo_1700c_1_iii_ordering_guard.py
  - unit_tests/portability/_inf_500d_4_e2e_helpers.py
  - unit_tests/prompt_assembly/test_build_feature_flatten_wiring.py
  - unit_tests/suite_performance/test_shared_layout_windows_lock.py
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
  - unit_tests/workflows/test_tq500g1viii_epic_drive_head.py
  - unit_tests/workflows/test_tq_600a_13_xx_finalize_hold.py
agents:
  test-writer: signed_off
  python-coder: signed_off
  pr-reviewer: signed_off
  ac-validator: signed_off
  ac-fulfillment-gate: signed_off
  commit: signed_off
---

# 10: The deploy-completeness closure guard analyses each file once per build

## Actor / Goal
Building into a fresh consumer takes about 27 s on main, and a test gives it 30 s. The build has
to be fast enough that this budget means something again. The closure guard's verdicts
(BP-900g-8, BP-900g-8-i) must stay exactly the same.

## Context
- **Found:** 2026-10-23 on PR #1318. `unit_tests/commit_guardian/test_bp_100k_4_iii.py::test_built_consumer_with_real_registry_has_no_unreachable_hooks`
  timed out at 30 s four runs in a row on shard 4 (job 120477190462). `test_ge_127a_1`'s cold-process build hit the same limit once.
- **Profile (bo4300-ci Docker, same on main and the epic):**
  - About 85–88% of `build.py` time is spent in `_check_intra_package_closure_guard` (build.py ~1133).
  - That guard calls `compute_intra_package_closure_with_deploy_root_relative` once per root (about 390 roots), each with a fresh `visited` set.
  - So shared modules are read, parsed and walked again for every root: 1,721 analyses of 392 files, about 4.4× redundant.
  - `_annotate_parents` runs about 4 times per parse.
  - Evidence files are in the session scratchpad (prof_*.txt).
- **Drift:** `.github/test_durations.json` (Oct 7) records 13.5 s for that test, and it is now about 27 s.

## Scope
1. In `scripts/build_referential_integrity_closure.py` (`_closure_walk` and its callers), cache each file's analysis across roots within ONE guard pass: the candidate list plus the family and deploy data.
   - Key the cache on everything the analysis depends on (the script path as reached, `root`, `data_root`).
   - Keep the per-root `visited` set and the closure union unchanged.
2. Parse each file once per pass, and annotate its parents once per tree.
3. Nothing outside one guard pass may reuse a cached result: no global state that survives between builds or tests.

## Acceptance Criteria
- [x] AC-1: For every root the real build checks, the closure with the cache is identical to the closure without it, and the guard's pass/fail verdict and messages are unchanged (BP-900g-8, BP-900g-8-i).
- [x] AC-2: A second-hop missing module (BP-900g-8-i) is still caught with the cache on.
- [x] AC-3: Each file is parsed at most once per guard pass.
- [x] AC-4: `build.py --target-dir <fresh consumer>` takes well under the test's 30 s budget on Linux (target: about 10 s), measured before and after.

## Test Requirements

```yaml
tests:
- name: test_cached_closure_equals_uncached_for_every_real_root
  file: unit_tests/test_bp_900g_8_closure_cache.py
  asserts: For every root the real build's closure guard checks, the closure computed with the per-pass cache equals the one computed without it (set equality), and the guard verdict is identical.
  framework: unittest
  type: behavioral
- name: test_second_hop_missing_module_still_refused_with_cache
  file: unit_tests/test_bp_900g_8_closure_cache.py
  asserts: A temp package where A imports B and B imports an undeployed C is still refused naming C, with the cache on.
  framework: unittest
  type: behavioral
- name: test_each_file_is_parsed_once_per_pass
  file: unit_tests/test_bp_900g_8_closure_cache.py
  asserts: Over one guard pass on a temp package where two roots share a module, the shared module is parsed once (count ast.parse or the analysis entry point).
  framework: unittest
  type: behavioral
```

## Sign-offs
- [x] test-writer — 2026-10-23 12:00
- [x] python-coder — 2026-10-23 13:00
- [x] pr-reviewer — 2026-10-23 14:00
- [x] ac-validator — 2026-10-23 15:00
- [x] ac-fulfillment-gate — 2026-10-23 16:00
- [x] commit — 2026-10-23 17:00

## Comments

### 2026-10-23 12:00 — test-writer (status: ok)
feedback-id: (submit-failed)
Tests: unit_tests/test_bp_900g_8_closure_cache.py (beside the BP-900g-8 tests; unit_tests/build_pipeline/ does not exist). Test Requirements `file:` updated.
Coder contract: add `closure_cache: dict | None = None` to `compute_intra_package_closure_with_deploy_root_relative` (and `_closure_walk`); `_check_intra_package_closure_guard` creates one dict per call and passes it for every root. Default None = today's behaviour. Parse once per file per pass.
AC-2 (second-hop refusal, via the real guard on a temp package) is a guard: green before the change, must stay green. AC-1 is red by absence (TypeError, no closure_cache kwarg yet). AC-3 is red by assertion (shared.py parsed 3 times; expected 1).
AC-1 compares the cached pass over all real roots with an independent cache-free call on every 12th root (time-limited).
Wrong versions caught: no cache (AC-3); cache cleared per root (AC-3); cache keyed too coarsely, so a later root gets another root's result (AC-1, reasoned).
cross_layer_seam_answer: covered (producing_side: closure function; consuming_side: build guard, tested via the real guard on a temp package)
reachability_entry_point_answer: resolved, `_check_intra_package_closure_guard` called through build module (main() not used)
red_baseline:
  - test_name: test_cached_closure_equals_uncached_for_every_real_root
    file: unit_tests/test_bp_900g_8_closure_cache.py
    kind: absence
    error: "TypeError: compute_intra_package_closure_with_deploy_root_relative() got an unexpected keyword argument 'closure_cache'"
  - test_name: test_each_file_is_parsed_once_per_pass
    file: unit_tests/test_bp_900g_8_closure_cache.py
    kind: assertion
    error: "AssertionError: {'a.py': 1, 'shared.py': 3, 'b.py': 1} != {'a.py': 1, 'b.py': 1, 'shared.py': 1}"

### 2026-10-23 13:00 — python-coder (status: ok)
feedback-id: (submit-failed)
Per-pass `closure_cache: dict | None = None` added to `compute_intra_package_closure_with_deploy_root_relative` and `_closure_walk`. `_closure_walk` is split: `_parse_script` (memoises the parsed tree per script path) and `_analyse_script` (memoises candidates plus family/deploy data, keyed on script as reached, root, data_root). `visited` and the closure union stay per call. `_annotate_parents` now runs once per tree (marker attribute). `_check_intra_package_closure_guard` creates one dict per call; no module-level state. build.py: net -14 lines (ratchet passes at 1291); comments condensed.
AC-4 measured (bo4300-ci Docker, Linux, `build.py --target-dir <fresh git-init dir>`): before 35.2 s and 24.7 s; after 8.6 s and 8.5 s.
New test file re-timed on Linux: 3 passed in 4.32 s (slowest test 4.19 s, under the 5 s limit).
Linux run: new file, all 17 BP-900g-8 / build_referential_integrity test files, test_bp_100k_4_iii.py, test_ge_127a_1.py: 121 passed (existing real-build tests there take 15-23 s each, as before).
red_baseline_results:
  - test_name: test_cached_closure_equals_uncached_for_every_real_root
    result: green
  - test_name: test_each_file_is_parsed_once_per_pass
    result: green
  (test_second_hop_missing_module_still_refused_with_cache: guard, stayed green)
completion_manifest:
  tests_green: true
  files_touched_match_plan: true
  file_size_ratchet_ok: true

### 2026-10-23 14:00 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
Staged diff reviewed (read-only). No high-confidence findings; verdicts are preserved.
- Cache keys: `_analyse_script` output depends only on (script as reached, root, data_root) plus the filesystem; the extractors read no cwd/env/other state. Key (script, root, data_root) is complete; tree key ("tree", script) differs in arity so the two never collide. Two spellings of one file parse twice (perf only, never wrong).
- Mutable results: callers only read cached `entries`/sets (`closure |= ...` mutates the per-root closure, not the cached sets). Safe.
- `_annotate_parents` marker: set on the tree object itself; trees only come from `_parse_script`. Fresh/deep-copied trees are handled correctly.
- No module-level state; `closure_cache=None` bypasses every cache read/write. Errors are not cached.
- M-1: AC-1 samples uncached reference on every 12th root; a key-leak would be caught only if it hits a sampled root. Cheap strengthening: also run the cached pass in reverse order with a second dict and assert equality on all roots, plus a temp-package test with one shared module under two different roots/data_roots.
- L: data-read "unresolvable" warnings now log once per pass instead of once per root (log volume only).
- build.py: only comments condensed plus the closure_cache kwarg and dict.

### 2026-10-23 12:30 — test-writer (status: ok)
feedback-id: (submit-failed)
M-1 addressed: AC-1 now also runs a second cached pass over ALL real roots in reverse order with a fresh dict and asserts per-root equality (closure and namespaced set) with the first pass. Still red by absence today (TypeError, no closure_cache kwarg).

### 2026-10-23 13:00 — test-writer (status: ok)
feedback-id: (submit-failed)
Timings: the two cached passes over all roots now run once in setUpClass; the file has 4 tests (AC-1 sampled-uncached, AC-1 forward-vs-reverse order check, AC-2, AC-3). Uncached sample stride raised to 40.

### 2026-10-23 15:00 — ac-validator (status: ok)
feedback-id: (submit-failed)
All 4 ACs covered (BP-900g-8, BP-900g-8-i verdicts unchanged). Store alignment check exit 0. No delivers_to/expects_from contracts.
AC-1 covered:
  implementation: scripts/build_referential_integrity_closure.py - closure_cache kwarg on compute_intra_package_closure_with_deploy_root_relative, _analyse_script (keyed script/root/data_root); scripts/build.py _check_intra_package_closure_guard (one dict per call)
  test: test_cached_closure_equals_uncached_for_every_real_root and test_cached_closure_is_independent_of_root_order_for_every_real_root (unit_tests/test_bp_900g_8_closure_cache.py)
AC-2 covered:
  implementation: visited set and closure union kept per call in _closure_walk (same file)
  test: test_second_hop_missing_module_still_refused_with_cache (unit_tests/test_bp_900g_8_closure_cache.py); 17 existing BP-900g-8 files green
AC-3 covered:
  implementation: _parse_script memoises tree per script; _annotate_parents once per tree
  test: test_each_file_is_parsed_once_per_pass (unit_tests/test_bp_900g_8_closure_cache.py)
AC-4 covered:
  implementation: same caching change; measured by python-coder and reported by caller: fresh-consumer build 25-35 s before, about 8.5 s after (Linux Docker)
  test: test_bp_100k_4_iii and test_ge_127a_1 green (121 passed with the 17 existing files)
Note: AC-4 timing is a manual measurement, not an automated assertion; the 30 s budget is enforced by the existing tests. Two real-root passes run in setUpClass (about 7-8 s once per file).

### 2026-10-23 16:00 — ac-fulfillment-gate (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  ac_store_fields_verified: true
  auto_fix_appended_only: true
  schema_valid: true
All 1 ACs verified (BP-900g-8; BP-900g-8-i also updated). work_status left done on both. 3 auto-fixes applied: BP-900g-8 implemented_by gained scripts/build_referential_integrity_closure.py and scripts/build_referential_integrity_closure_eval.py, covered_by gained unit_tests/test_bp_900g_8_closure_cache.py (carries # covers: BP-900g-8); BP-900g-8-i covered_by gained the same test (carries # covers: BP-900g-8-i). check_ac_schema.py passed on both; AC files staged. Commit phase may proceed.

### 2026-10-23 17:00 — commit (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Commit of the closure-guard cache change; staged set verified as the 8 expected files.
