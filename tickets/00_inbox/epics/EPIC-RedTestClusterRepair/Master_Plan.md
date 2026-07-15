---
title: "EPIC: Make the pytest suite green + trustworthy so the CI test gate can block"
type: epic
status: todo
components:
  - testing_quality
  - build_pipeline
  - commit_guardian
created: 2026-07-15
depends_on: []
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
---

# EPIC: Residual Red-Test Repair + Trustworthy Blocking Gate

## Goal

Drive the leafcutter-ai pytest suite to genuinely green on a fresh `origin/main`,
and make that green **trustworthy** (no xfail-masking hiding real failures), so the
CI `test` job can be flipped to blocking (BP-1200b) and added to branch protection
(BP-1200c). This epic owns **only the residual** not fixed by the salvage PR #300 or
the two 2026-07-14 build_pipeline audit epics — see the evidence-based coverage map.

## Context — how this scope was derived

A 5-agent review (2026-07-15) mapped every failing test on `origin/main` CI (run
`29405520992`: `81 failed, 3116 passed, 10 skipped, 27 xfailed`) against the salvage
PR #300, the phantom-remediation epic, and the backfill epic. Two critical findings
shaped this epic:

1. **A `pytest_ac_enforcement` plugin (`pytest.ini` `addopts`) xfail-masks any failing
   test whose covering AC's `work_status != "done"`** (unless `AC_ENFORCE_STRICT=1`).
   So the true failure set is LARGER than the CI "81 failed" — several genuinely-broken
   tests hide in the "27 xfailed" bucket. Any real health check must run with
   `AC_ENFORCE_STRICT=1` (or `-o addopts=""`). This is why the user's named files
   (`test_readiness_gate`, `test_check_ac_done_on_merge`, `test_generate_ticket_from_ac`)
   were "invisible" in the CI failed count.
2. **Salvage PR #300 originally contained a production regression** (it reverted the E2
   `plan-feature.js` source to E1 and masked the guard) — now corrected (commit
   `a9819e15`). The correction means the plan-feature **deployed** copy is still stale,
   so its parity tests are residual here (ticket 07).

## Coverage map (verified by running each file in the salvage worktree)

**Owned by SALVAGE PR #300 (`salvage/testsuite-green-clusters`) — NOT in this epic:**
build-module shadow cluster via the `unit_tests/build → build_guards` rename
(`test_build_package_version`, `test_build_guard_real_package`, `test_build_version_wiring`,
`test_build_changelog_placeholder`, 6/7 of `test_build_tracked_source_guard`),
`test_setup_ticket_worktree`, `test_workflow_variant_transform`,
`test_check_surface_components_e3`, `test_skill_registry`, `test_build_artifact_parity`,
`test_transform_hooks_and_autofix_emission`. **Gate: #300 must merge for these.**

**Owned by EPIC-BuildPipelinePhantomRemediation (on origin/main) — NOT in this epic:**
`test_build_tracked_source_guard::…bp900c3` (ticket 01, BP-900c-3); the CI gate flip
BP-1200b (ticket 05); deployed hook parity BP-100i-3 (ticket 03).

**Already GREEN (no fix) — verify only:** `test_check_components_minimum_schema`
(25 pass + 1 intentional in-file xfail).

**Residual — owned by THIS epic:**

| # | File | Failing tests | Root cause | Named? |
|---|------|---------------|------------|--------|
| 01 | [01_ac_schema_components_and_axes.md](./01_ac_schema_components_and_axes.md) | `test_check_ac_schema` (13), `test_readiness_gate` (3) | post-#277 schema tightening: `components` now required + `change_target`/`risk_surface`/`pattern_slots`/`implements_pattern`/free-form `origin_agent` not accepted; `validate_manually()` stricter than schema | ✅ readiness_gate, check_ac_schema |
| 02 | [02_create_check_ac_done_on_merge_hook.md](./02_create_check_ac_done_on_merge_hook.md) | `test_check_ac_done_on_merge` (3) | hook script `check_ac_done_on_merge.py` does not exist anywhere (AC ACD-600b) | ✅ check_ac_done_on_merge |
| 03 | [03_agent_template_produces_frontmatter.md](./03_agent_template_produces_frontmatter.md) | `test_generate_ticket_from_ac` (1) | `sql-view-creator.md` (+audit all templates) missing `produces:` in YAML frontmatter (BO-510-2/4) | ✅ generate_ticket_from_ac |
| 04 | [04_commit_classifier_import_cache.md](./04_commit_classifier_import_cache.md) | `test_defect_fixes` (2) | `classify_staged_files()` caches config at import time, not per call (BO-1100c-4) | |
| 05 | [05_verify_precommit_active.md](./05_verify_precommit_active.md) | `test_verify_precommit_active` (2) | `hook_freshness` check / deployed `verify_precommit_active.py` | |
| 06 | [06_psutil_dev_dependency.md](./06_psutil_dev_dependency.md) | `test_sweep_processes` (1) | `psutil` absent from `requirements-dev.txt` (CI has no psutil) | |
| 07 | [07_deployed_plan_feature_e2_parity.md](./07_deployed_plan_feature_e2_parity.md) | `test_partial_run_recovery` (3), `test_final_gate_and_commit_message` (1), `test_commit_stage_output_behavioral` (1), `test_build_phases` (2) | deployed `scripts/workflows/plan-feature.js` is stale E1 vs the E2 source template — regenerate deployed from source (the proper fix #300 deferred) | |
| 08 | [08_anti_build_shadow_guard.md](./08_anti_build_shadow_guard.md) | (regression guard) | make the `build→build_guards` rename stick: guard test + update backfill tickets + retarget #287's new test | |
| 09 | [09_trustworthy_gate_unmask.md](./09_trustworthy_gate_unmask.md) | (gate integrity) | the blocking gate must not be fooled by `pytest_ac_enforcement` xfail-masking | |
| 10 | [10_fresh_clone_green_verification.md](./10_fresh_clone_green_verification.md) | (verification) | confirm fresh-clone green under strict mode; re-diagnose; hand off to BP-1200b | |

## Salvage dependency (blocking gate for this epic)

This epic's coverage map assumes **PR #300 merges**. If it does not, the clusters it
owns fall back to unowned — re-scope them here. Do not close this epic until #300 (or
an equivalent) has landed and CI is re-diagnosed (ticket 10).

## Recommended merge order (from risk review)

1. Close competing PR #301 (partial duplicate of #300).
2. Merge #300 (corrected). Verify no `unit_tests/build/test_*.py` remain.
3. Land this epic's fixes (tickets 01–09), driven in isolated worktrees off `origin/main`.
4. Ticket 10: confirm fresh-clone green **under `AC_ENFORCE_STRICT=1`**.
5. THEN EPIC-BuildPipelinePhantomRemediation ticket 05 flips BP-1200b — never before 4.

## Parallel-safety

Tickets touch disjoint files (see each `files_touched`). 01/02/05/09 touch
`commit_guardian`/AC-store code; 07 touches workflow JS; 03 touches an agent template;
04 touches `commit_classifier`; 06 touches `requirements-dev.txt`; 08 touches
`unit_tests/` layout + backfill tickets. No cross-ticket file overlap → parallel-safe.

## Test-truth guardrail (applies to every ticket)

Every ticket's exit criteria require the assertion to still verify the **real invariant**,
proven against the **real artifact** in a fresh process — not greened by weakening or
deleting the check, and not by adding an xfail. Green sign-off proves the code runs, not
that it works (this repo's recurring phantom-done failure mode).

## Drive outcome — 2026-07-15 (`/build-feature`)

**Verified GREEN (target tests re-run unmasked with `-o addopts=""`) and landed:**
tickets **01, 02, 03, 04, 06, 08, 09** — real fixes, not phantom-done.

**Deferred — still `todo`, NOT done:**

- **05 (`verify_precommit_active`)** — the drive's coder made `hook_freshness`
  *advisory*, which **broke** `test_stale_hook_appends_hook_freshness_to_failing_checks`
  (a test-weakening the anti-weakening AC forbids). That commit was **reverted**. Proper
  fix: make freshness detection actually correct so both `test_all_checks_pass` AND the
  stale-detection test pass — do **not** make the check advisory. Separately, the file's
  `test_ac_e2_run_hook_resolver...` needs `scripts.commit_guardian.run_hook` (**BO-1700e-2**,
  a different AC) — decide whether that belongs here or in its own ticket.
- **07 (deployed `plan-feature.js` parity)** — the coder died on a transient API error
  mid-edit, leaving a `SyntaxError: Illegal return statement` in the deployed file
  (a botched E1→E2 hand-conversion). Partial work **discarded**. Proper fix: **regenerate**
  the deployed `scripts/workflows/plan-feature.js` from the E2 source template via the
  build's workflow-deploy transform — NOT by hand-editing. Requires the build environment
  (`build.py` hangs under WSL; run on a Linux/CI box).
- **10 (verification)** — not run (was gated behind 07). Re-run once 05 + 07 land, under
  `AC_ENFORCE_STRICT=1` on a fresh checkout.
