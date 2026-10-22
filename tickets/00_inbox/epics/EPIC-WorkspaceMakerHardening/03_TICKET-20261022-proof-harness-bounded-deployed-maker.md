---
title: "The proof harness runs the deployed maker in a bounded environment, proves the marker survives the real build, runs the family in CI and records timings"
ac_traceability:
  ac_path: docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces
  l2:
  - BO-4300c-2
  - BO-4300f-4
  - BO-4300a-1
  l3:
  - BO-4300f-4-i
status: todo
components:
  - worktree_manager
  - build_orchestration
  - testing_quality
created: '2026-10-22'
last_updated: '2026-10-22'
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
change_target: code
risk_surface: internal
complexity: high
requires_adr: false
requires_diagram: false
tags:
  - BO-4300
  - bo4300-hardening
  - M15
  - M14
  - N3
  - N4
  - P8
files_touched:
  - unit_tests/build_orchestration/_workspace_maker_fixtures.py
  - unit_tests/build_orchestration/_workspace_maker_builders.py
  - unit_tests/build_orchestration/_workspace_maker_build_helpers.py
  - scripts/suite_performance/_shared_layout_producer.py
  - unit_tests/build_orchestration/test_bo_4300a_1_deployed.py
  - unit_tests/build_orchestration/test_bo_4300f_4.py
  - unit_tests/build_orchestration/_bo_4300f_2_fixtures.py
  - .github/workflows/ci.yml
  - unit_tests/build_orchestration/test_bo_4300a_1_budgets.py
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  ac-validator: needed
  ac-fulfillment-gate: needed
  commit: needed
---

# 03: The proof harness runs the deployed maker in a bounded environment, proves the marker survives the real build, runs the family in CI and records timings

## Actor / Goal
A maintainer trusts the maker's proofs. They run the DEPLOYED maker from one shared real build, with an
isolated git configuration and closed stdin. They run on every PR that touches the maker. They show that
the real install build leaves the maker's own `.leafcutter/` state intact, and they record how fast the
verbs are.

## Context
- **Defect M15 (LOW-MEDIUM): test-harness hygiene.**
  - **ACs violated:** the BO-4300c-2 test ITs ("Tests must not spawn the package's own scripts/build.py";
    "run git with an isolated global and system config", which applies to the maker process too) and
    BO-4300f-4 / f-4-i.
  - **Where, verified against the current tree:**
    - `unit_tests/build_orchestration/_workspace_maker_fixtures.py:107` `ensure_deployed_layout` spawns
      `scripts/build.py --target-dir <mkdtemp>` once per interpreter, i.e. once per xdist worker. It never
      cleans up and does not use the session's shared reference layout.
    - `_bo_4300a_1_fixtures.DeployedMakerBuild.build` (line ~289) already delegates to it, so fixing the
      helper fixes both.
    - `run_maker` (`_workspace_maker_fixtures.py:262`) starts from `dict(os.environ)` and inherits stdin.
    - `_workspace_maker_builders.py:260` has `_LINK = "work" + "tree"`. Splitting the string hides
      `link_checkout`'s raw command from the BO-4300f-2 census. The census exemption list is
      `EXEMPTIONS` in `unit_tests/build_orchestration/_bo_4300f_2_fixtures.py:39`, and it already exempts
      `_workspace_maker_builders.py` with a reason that names only `legacy_worktree`.
- **P8 (port).** Base `ensure_deployed_layout` on the session's ONE shared deployed layout,
  `scripts/suite_performance/_shared_layout_producer.get_or_produce_shared_layout()` (line 270; the pytest
  fixture surface is `pytest_shared_reference_layout.shared_reference_layout`).
  - The handover listed `_shared_layout_producer.py` under `unit_tests/build_orchestration/`; it actually
    lives at `scripts/suite_performance/_shared_layout_producer.py`.
  - Keep v2's names (`ensure_deployed_layout`, `deployed_maker_path`, `run_maker`) as shims.
  - v1 reference: 0dbdaf2ca, `_workspace_maker_fixtures` `deployed_layout` / `_validated` / `_env_for` /
    `run_maker`.
- **N3 (A12): BO-4300a-1 IT9 and ADR-018 A1.4.** The real install build must leave
  `.leafcutter/workspace.json` intact. The amended IT9 adds every other folder the maker keeps inside
  `.leafcutter/`, i.e. `.leafcutter/rescue/` (shipped by `templates/scripts/worktree_ensure_state.py`,
  `_RESCUE`, line 57).
  - Today this is proven only through a stub build.
  - Pre-seed a marker and a rescue folder in the shared layout's target before its ONE real build
    (`_shared_layout_producer._run_build_subprocess` line 156 / `_produce` line 217), then assert that both
    survive byte-identical. This is that build, not an extra spawn.
  - Check that `shared_layout_integrity.py` / `_shared_layout_integrity_compare.py` do not flag the
    pre-seeded files.
- **M14 (A11, option 2): a new BO-4300f-4 IT.**
  - The 9 `_MANUAL` tests in `test_bo_4300a_1_deployed.py` (lines 134-439) and the 2 in `test_bo_4300f_4.py`
    (lines 112, 178) are deselected in every CI shard by pytest.ini's `-m "not manual ..."`.
  - Add a DEDICATED job to `.github/workflows/ci.yml`. It runs this family's deployed-maker tests
    (manual-marked included) on every PR that changes:
    - `templates/scripts/worktree*.py` or `templates/scripts/workspace_root.py`;
    - the maker's deploy-manifest entries (`scripts/build_phases_script_deploy_standalone.py`,
      `scripts/build_deploy_manifest_helpers.py`);
    - this family's tests and fixtures.
  - A test it does not run is reported as not run, never as passed.
  - Precedent: the existing `workspace-maker-windows` job (ci.yml ~line 443).
  - The lint step "Refuse a deselection with no invoked opt-in (TQ-600a-13-i)"
    (`scripts/suite_performance/check_exclusion_compensation.py`) must still pass.
- **N4 (A13, option 2): BO-4300a-1 IT12.** Excluding the install build, `ensure` on a generated fixture
  project of 8,500 tracked files with the stub build is budgeted 30 s. `locate`, `list`, `verify` and
  `where` are budgeted 5 s each. The test records the measured timings and fails only above 2x the budget,
  naming the verb and the time.

## Scope
1. Rebase `ensure_deployed_layout()` on the shared layout producer. No new `build.py` spawn; the mkdtemp
   spawn is removed.
2. Make `run_maker` run the maker with `stdin=subprocess.DEVNULL` and a bounded environment:
   - `_isolated_git_env()` (isolated `HOME`/`USERPROFILE`/`GIT_CONFIG_GLOBAL`, `GIT_CONFIG_NOSYSTEM=1`);
   - `GIT_CEILING_DIRECTORIES` set to the fixture's parent;
   - the caller's `env` merged on top.
3. Remove `_LINK`, spell the command literally in `_run_link`, and extend the existing `EXEMPTIONS` entry's
   reason to name `link_checkout` / `unlink_checkout`. The census (`python -m
   unit_tests.build_orchestration.test_bo_4300f_2 --census`) still prints nothing.
4. Pre-seed the marker and rescue sentinel in the shared layout producer before its one build. Add the
   survival test to `test_bo_4300a_1_deployed.py`.
5. Add the dedicated CI job, with a path filter. It is informational unless the user adds it to the
   required checks.
6. Add `test_bo_4300a_1_budgets.py`. It builds 8,500 tracked files with `make_project(..., stub_build=...)`
   and prints one timing line per verb. The test exceeds `testing_context.max_test_duration_seconds`, so it
   carries the `_MANUAL` suffix and runs in the dedicated job (and in done-proof, which already opts linked
   `_MANUAL` tests in).

## Acceptance Criteria
- [ ] AC-1: BO-4300c-2 (test IT: no spawn of the package's own build.py). In a full run of
  `unit_tests/build_orchestration/test_bo_4300*.py`, `scripts/build.py` is spawned only by the shared layout
  producer, at most once per run. `ensure_deployed_layout()` returns the shared layout's root.
- [ ] AC-2: BO-4300c-2 (test IT: isolated global and system config, closed stdin). `run_maker` starts the
  maker with stdin closed, `GIT_CONFIG_NOSYSTEM=1`, an isolated `GIT_CONFIG_GLOBAL`/`HOME`, and
  `GIT_CEILING_DIRECTORIES` set.
- [ ] AC-3: BO-4300f-4-i / f-2 census. No string-splitting trick remains in the f-4 fixture family. The
  census exemption for `_workspace_maker_builders.py` carries a reason that names `link_checkout`, and the
  census prints nothing.
- [ ] AC-4: BO-4300a-1 IT9 (A12). After the shared layout's one real build, the pre-seeded
  `.leafcutter/workspace.json` and `.leafcutter/rescue/` (manifest and copied file) are byte-identical to
  what was seeded.
- [ ] AC-5: BO-4300f-4 (A11). A CI job runs every deployed-maker test of this family, `_MANUAL` included, on
  PRs that change the maker's files, the maker's deploy-manifest entries or this family's tests. A
  deselected or skipped test is listed as not run in the job output.
- [ ] AC-6: BO-4300a-1 IT12 (A13). The budget test prints the measured seconds for `ensure`, `locate`,
  `list`, `verify` and `where` on an 8,500-file fixture. It fails only when a verb exceeds 2x its budget
  (60 s / 10 s), naming the verb and the measured time.

## Test Requirements

```yaml
tests:
- name: test_deployed_layout_is_the_shared_layout_and_spawns_no_build
  file: unit_tests/build_orchestration/test_bo_4300f_4.py
  covers:
  - BO-4300f-4
  - BO-4300c-2
  asserts: >-
    ensure_deployed_layout() equals get_or_produce_shared_layout() and the
    deployed_maker_path() lies under it. A second call spawns nothing (subprocess.run patched to count
    build.py invocations after the first resolution).
  framework: unittest
  type: behavioral
- name: test_run_maker_closes_stdin_and_isolates_git_config
  file: unit_tests/build_orchestration/test_bo_4300f_4.py
  covers:
  - BO-4300c-2
  - BO-4300f-4-i
  asserts: >-
    run_maker running a tiny probe maker copy (maker_path seam) that dumps its stdin state and env shows
    stdin at EOF, GIT_CONFIG_NOSYSTEM=1, GIT_CONFIG_GLOBAL not the real user's, and
    GIT_CEILING_DIRECTORIES set.
  framework: unittest
  type: behavioral
- name: test_link_checkout_exemption_is_declared_with_a_reason
  file: unit_tests/build_orchestration/test_bo_4300f_4.py
  covers:
  - BO-4300f-4-i
  asserts: >-
    _workspace_maker_builders.py contains no split command string. Its EXEMPTIONS entry in
    _bo_4300f_2_fixtures names link_checkout in its reason, and fx.census over the repo returns [].
  framework: unittest
  type: behavioral
- name: test_real_install_build_leaves_marker_and_rescue_folder_intact_MANUAL
  file: unit_tests/build_orchestration/test_bo_4300a_1_deployed.py
  covers:
  - BO-4300a-1
  asserts: >-
    In the shared layout produced by its one real build, the producer's pre-seeded
    .leafcutter/workspace.json and .leafcutter/rescue/manifest.json plus the rescued file are
    byte-identical to the seeded bytes.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_verb_timings_are_recorded_and_fail_only_above_twice_budget_MANUAL
  file: unit_tests/build_orchestration/test_bo_4300a_1_budgets.py
  covers:
  - BO-4300a-1
  asserts: >-
    make_project with a generated 8,500-file tracked tree and the stub build. run_maker times ensure
    (excluding the stub install), locate, list, verify and where, and prints "<verb> <seconds>" lines. It
    asserts each is <= 2x budget (ensure 60 s, the others 10 s), and the failure message names the verb
    and the measured time.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_ci_has_a_dedicated_deployed_maker_job_with_path_filter
  file: unit_tests/build_orchestration/test_bo_4300f_4.py
  covers:
  - BO-4300f-4
  asserts: >-
    .github/workflows/ci.yml has a job that runs on pull_request, filters on templates/scripts/worktree*.py,
    templates/scripts/workspace_root.py, the deploy-manifest files and this family's tests, and runs pytest
    with a -m selection that includes manual tests over test_bo_4300a_1_deployed.py, test_bo_4300f_4.py
    and test_bo_4300a_1_budgets.py, reporting deselected or skipped tests.
  framework: unittest
  type: behavioral
```

## Sign-offs
- [ ] test-writer
- [ ] python-coder
- [ ] pr-reviewer
- [ ] ac-validator
- [ ] ac-fulfillment-gate
- [ ] commit

## Comments

_(Append-only log -- leave blank when authoring.)_
