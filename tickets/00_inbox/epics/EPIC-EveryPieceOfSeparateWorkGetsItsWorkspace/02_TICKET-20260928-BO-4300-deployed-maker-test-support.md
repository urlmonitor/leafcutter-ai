---
title: 'Proof runs the deployed maker: shared test locator, fixtures and developer-repo guard'
status: todo
components:
- worktree_manager
- testing_quality
created: '2026-09-28'
last_updated: '2026-09-28'
depends_on: []
priority: critical
roadmap_phase: phase_1
advances_current_outcome: true
change_target: code
risk_surface: internal
complexity: medium
requires_adr: false
requires_diagram: false
source_ac: BO-4300f-4
ac_traceability:
  ac_path: docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces
  l2:
  - BO-4300f-4
  l3:
  - BO-4300f-4-i
ac_coverage: 0/2
tags:
- BO-4300
- re-cut-2026-09-28
files_touched:
- unit_tests/build_orchestration/_workspace_maker_fixtures.py
- unit_tests/build_orchestration/_developer_repo_guard.py
- unit_tests/build_orchestration/conftest.py
- unit_tests/build_orchestration/README.md
- unit_tests/build_orchestration/test_bo_4300f_4.py
- unit_tests/build_orchestration/test_bo_4300f_4_i.py
- unit_tests/build_orchestration/_bo2400f13_fixtures.py
- unit_tests/build_orchestration/test_bo2400f_13_occupied_workspace_refusal.py
- unit_tests/build_orchestration/test_bo2400f_13i_own_leftover_report.py
- unit_tests/build_orchestration/test_bo2400f_13ii_foreign_occupant.py
- unit_tests/build_orchestration/test_bo2400f_13iii_refusal_is_inert.py
- unit_tests/build_orchestration/test_bo2400f_13iv_free_location_proceeds.py
- unit_tests/build_orchestration/_bo_4300a_1_fixtures.py
- unit_tests/build_orchestration/test_bo_4300a_1_deployed.py
agents:
  ac-fulfillment-gate: needed
  ac-validator: needed
  architect-review: needed
  commit: needed
  documentation-expert: not_needed
  documentation-verifier: not_needed
  frontend-coder: not_needed
  pr-reviewer: needed
  pull-request: not_needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  test-writer: needed
  user-surface-smoker: not_needed
---

# 02: Proof runs the deployed maker: shared test locator, fixtures and developer-repo guard

## Actor / Goal

In order to prove every later BO-4300 behaviour against the copy of the maker a project actually receives, we need one shared test support module and a session guard, so that no proof can pass against a stray tracked copy and no proof can leak worktrees or config into the developer's own repository.

## Context

Every maker AC's it_requirements say 'resolved through the shared test locator delivered by BO-4300f-4'. In the failed run this producer was ticket 58 of 59, so every earlier test ticket built its own stand-in (`_bo_4300a_1_fixtures.py`, `_bo_4300a_1_ii_fixtures.py`, ...) and ticket 56 blocked on its absence. It is therefore first in the re-cut order.

Part of `EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace`, re-cut on 2026-09-28 by deliverable (see Master_Plan.md, 'Re-cut 2026-09-28'). This ticket owns the files in `files_touched` and covers 2 AC(s); the AC YAML records under `docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/` are the source of truth and win over any text here.

## AC References

| # | AC | Level | Title | Expects from | Producing ticket |
|---|----|-------|-------|--------------|------------------|
| AC-1 | BO-4300f-4-i | L3 | Running the proof leaves the developer's own project unchanged | BO-4300f-4 | this ticket |
| AC-2 | BO-4300f-4 | L2 | The proof runs the copy of the maker that a project actually receives | BO-4300a-1 | 01_TICKET-20260927-BO-4300a-1.md |

**Closure order.** Children are listed before their parents. Composite(s) `BO-4300f-4` close only after every child listed in their `covered_by` is done (`check-done-proof`); all of those children are in this ticket, so no parent here waits on another ticket. `source_ac` (`BO-4300f-4`) is the anchor `check-ticket-ac-status-parity` checks; `ac_traceability` (list form) names every AC so `ac-fulfillment-gate` verifies each one before commit. The ticket may be set `done` only when every AC above is `work_status: done`.

## Acceptance Criteria

### AC-1: BO-4300f-4-i (L3) -- Running the proof leaves the developer's own project unchanged

```gherkin
Given the developer's own project, with its registered workspaces, branches and
  version-control settings recorded,
When the whole workspace proof suite runs from inside that project,
Then its registered workspaces, branches and version-control settings are
  identical afterwards,
And no temporary project or workspace made by the suite is registered in, or
  linked from, the developer's project.
```

### AC-2: BO-4300f-4 (L2) -- The proof runs the copy of the maker that a project actually receives

```gherkin
Given the workspace maker's proof suite, and a deliberate fault placed only in
  the copy of the maker that an install delivers, with its source left correct,
When the proof suite runs,
Then it fails, naming the behaviour the fault broke,
And the suite runs the delivered maker as a separate process from each starting
  point in BO-4300b-1, against real test projects with a real shared project,
  with no stand-in for version control.
```

- [ ] AC-1: BO-4300f-4-i -- Running the proof leaves the developer's own project unchanged
- [ ] AC-2: BO-4300f-4 -- The proof runs the copy of the maker that a project actually receives

## Test Requirements

Taken from each AC's `test_spec` (one test module per AC); the last entry is the ticket's reachability proof. Every test carries `# covers: <AC-ID>` and `# angle: <angle>`.

```yaml
tests:
- name: test_developer_repo_registrations_branches_and_config_unchanged_by_suite
  file: unit_tests/build_orchestration/test_bo_4300f_4_i.py
  covers:
  - BO-4300f-4-i
  asserts: The before/after snapshots of the developer repository are identical.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files: []
- name: test_no_temporary_project_is_registered_in_or_linked_from_developer_repo
  file: unit_tests/build_orchestration/test_bo_4300f_4_i.py
  covers:
  - BO-4300f-4-i
  asserts: No worktree entry, remote, alternates file or config value in the developer repository points
    into the suite's temp directory.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files: []
- name: test_fault_only_in_deployed_copy_fails_the_suite_naming_the_behaviour
  file: unit_tests/build_orchestration/test_bo_4300f_4.py
  covers:
  - BO-4300f-4
  asserts: With a fault injected into a copy of the deployed maker (source untouched), the proof subset
    fails with a message naming the broken behaviour.
  framework: unittest
  type: behavioral
  angle: deployed
  implementation_files: []
- name: test_suite_runs_deployed_maker_as_separate_process_from_every_starting_point
  file: unit_tests/build_orchestration/test_bo_4300f_4.py
  covers:
  - BO-4300f-4
  asserts: The locator returns the install path (not templates/), and runs from each of the six starting
    points spawn a separate process against real repos.
  framework: unittest
  type: behavioral
  angle: seam
  implementation_files: []
- name: test_locator_fails_when_deployed_copy_is_absent
  file: unit_tests/build_orchestration/test_bo_4300f_4.py
  covers:
  - BO-4300f-4
  asserts: Pointing the locator at a layout without the maker raises a failure, not a skip.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files: []
- name: test_locator_never_resolves_a_tracked_source_copy
  file: unit_tests/build_orchestration/test_bo_4300f_4.py
  covers:
  - BO-4300f-4
  asserts: Pointing the locator's override seam, or its search, at the package repository's scripts/ or
    templates/scripts/ copy of the maker raises a failure naming that path; only an install-layout path
    is accepted.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files: []
- name: test_ticket_02_reachable_from_entry_point
  file: unit_tests/build_orchestration/test_bo_4300f_4_i.py
  covers:
  - BO-4300f-4
  angle: reachability
  surface_invoked: python -m pytest unit_tests/build_orchestration (the whole workspace proof suite, as
    a subprocess inside an isolated fixture repo, with a deliberately leaking test)
  asserts: Invoke the production entry point named in surface_invoked (never an import of the function)
    and assert the new behaviour occurs and is consumed.
  implementation_files: []
```

## Implementation Notes

### Ticket-specific (harvested from the failed run and the AC records)

- LOCATOR: resolve the DEPLOYED maker from the shared deployed layout produced by CI's `python scripts/build.py --target-dir .` (i.e. `<repo>/.leafcutter/scripts/worktree.py` and `workspace_root.py`), FAIL (never skip, never fall back to `templates/` or `scripts/`) when absent. Override seam used only by the meta-test (copy deployed maker, inject a fault into the copy, run a proof subset, require it to fail naming the broken behaviour).
- BUILDERS: bare hub + project, dev and consumer layouts, a stub build entry point that installs a real rejecting hook in well under a second, helpers for every BO-4300b-1 starting point (ticket 04 consumes these), and the ONE legacy-worktree helper (real `git worktree` registration; the census exemption ticket 14 declares; consumed by ticket 12).
- RE-POINT: `_bo2400f13_fixtures.py` sets `DEPLOYED_SCRIPT = _REPO_ROOT / 'scripts' / 'setup_ticket_worktree.py'` (the tracked copy). Re-point it and its five users at the deployed layout through the locator (their final migration to the maker is ticket 14's). Migrate `_bo_4300a_1_fixtures.py` / `test_bo_4300a_1_deployed.py` onto the locator: its `setUpClass` currently spawns `scripts/build.py --target-dir <tmp>`, which the 'Tests must not spawn their own build.py' rule forbids (01 test-writer flagged the migration as owed).
- GUARD: session-scoped autouse fixture in `unit_tests/build_orchestration/conftest.py`, snapshotting `git worktree list --porcelain`, `git for-each-ref`, `git config --local --list` of the developer repo before/after; fixture git runs with isolated HOME / GIT_CONFIG_GLOBAL / GIT_CONFIG_NOSYSTEM. The guard module lives in `unit_tests/build_orchestration/_developer_repo_guard.py` (test support), NOT under `scripts/`: in the failed run it sat at `scripts/build_orchestration/developer_repo_guard.py` and, while untracked, tripped `scripts/build.py`'s TRACKED-SOURCE GUARD for every other ticket's proof run (14 test-runner).
- RISK FROM THE FAILED RUN: the guard raised `DeveloperRepoChangedError` intermittently because other agent sessions changed the shared developer repo during the run (43 test-writer, 04 test-writer). Decide and document how the guard distinguishes the suite's own leaks from concurrent sessions (e.g. snapshot only refs/worktrees under the suite's temp roots, or require the suite to run from an isolated clone) without weakening BO-4300f-4-i's 'any difference fails the session'. Raise it at architect-review.
- STARTING POINT (re-verify, do not trust): `git show refs/wip/bo4300-attempt1:unit_tests/build_orchestration/conftest.py`, `refs/wip/bo4300-attempt1:scripts/build_orchestration/developer_repo_guard.py`, `refs/wip/bo4300-attempt1:unit_tests/build_orchestration/test_bo_4300f_4_i.py`.
- USER DECISIONS (2026-09-28) THE FIXTURES MUST FOLLOW: Q5 -- `make_project` reports `landing_place` as the sibling landing root `<parent of project>/<project dir name>-worktrees/` (the maker's own rule lands in ticket 04; the fixture never hard-codes the old `<parent>/worktrees/`). Q4 -- `legacy_worktree(project, name, unsent=False, at=None)` takes the branch name as given (so tests can use legacy spellings such as `EPIC-Alpha`) and by default places the worktree where the old way put it, outside the new landing root, so tickets 06 (BO-4300d-3-i) and 12 (BO-4300f-3) can prove an old workspace is never twinned.

### AC technical requirements (verbatim from the AC store; shared boilerplate omitted)

**BO-4300f-4-i**

- A session-level guard snapshots the developer repository (`git worktree list --porcelain`, `git for-each-ref`, `git config --local --list`) before the workspace proof suite and compares after; any difference fails the session. Fixture git runs with isolated HOME / GIT_CONFIG_GLOBAL / GIT_CONFIG_NOSYSTEM so no fixture identity reaches the real config.

**BO-4300f-4**

- Deliver the shared test support module (e.g. unit_tests/build_orchestration/_workspace_maker_fixtures.py): (1) a locator that resolves the DEPLOYED maker from the shared deployed layout (the CI build step's `build.py --target-dir .`, or TQ-600a's session-scoped layout once it lands) and FAILS -- never skips, never falls back to templates/ -- when it is absent; (2) an override seam used only by the meta-test to point at a faulted copy; (3) fixture builders for real temp projects with a bare hub, the dev and consumer layouts, a stub build entry point installing a real rejecting hook, and helpers for every BO-4300b-1 starting point.
- Meta-test: copy the deployed maker, inject a fault only into the copy (source unchanged), run the relevant proof subset against it via the override seam, and require that it fails naming the broken behaviour.
- Delete or re-point tests that exercise the tracked scripts/ copy as 'DEPLOYED_SCRIPT' (unit_tests/build_orchestration/_bo2400f13_fixtures.py and its users).
- NO SECOND COPY (KI-TQ-20260831-mutation-probe-lands-in-the-wrong-copy, KI-TQ-004): the locator resolves only the DEPLOYED maker and resolver module; it never accepts a path under the package repository's scripts/ or templates/ as the maker, so a tracked stray copy can never become the thing under test (the mutation probe of KI-TQ-20260831 landed in the wrong copy for exactly this reason). The tracked-file test that forbids a copy outside templates/scripts/ is BO-4300a-1's; this record keeps the locator from ever reaching one.
- The fixture module also owns the ONE legacy-worktree fixture helper (a real `git worktree` registration in a temp project, for BO-4300f-3's cut-over tests and for tests that migrate off hand-built worktrees under BO-4300f-2's census). It is the census's only test-side exemption; no other test spells the worktree add/remove commands.
- Git spelling in fixtures (KI-CG-20260925-commit-delegation-hook-misses-git-dash-c): fixture commits run git with its working directory set to the repository, never as `git -C <path> commit`; -C is used only with non-commit verbs.

## Agent Contracts

### python-coder

- [ ] AC-1: BO-4300f-4-i -- Running the proof leaves the developer's own project unchanged
- [ ] AC-2: BO-4300f-4 -- The proof runs the copy of the maker that a project actually receives

**Depends on:** test-writer's red baseline for the tests above and the producers under Expects From.

### test-writer

- [ ] AC-1: red tests for BO-4300f-4-i per `## Test Requirements`
- [ ] AC-2: red tests for BO-4300f-4 per `## Test Requirements`

**Delivers to:** python-coder (red baseline).

### Expects From

- **BO-4300f-4-i <- BO-4300f-4** (this ticket): Fixture API.
- **BO-4300f-4 <- BO-4300a-1** (01_TICKET-20260927-BO-4300a-1.md): Maker deployed by a named deploy-manifest entry to <install>/scripts/worktree.py.

### Delivers To

- **BO-4300f-4 -> test-writer**: Fixture API used by every maker proof in this family: deployed_maker_path() -> absolute path (raises when absent); make_project(tmp, layout='dev'|'consumer', stub_build=..., hook='reject'|'accept') -> {project, hub, landing_place} where landing_place is the Q5 landing root <parent of project>/<project dir name>-worktrees/ (decided 2026-09-28); run_maker(args, cwd, env=None, timeout=...) -> {answer: dict, exit_code: int, stdout: str, stderr: str}, failing the test when stdout is not exactly one JSON object; starting_points(project) -> dict of the six BO-4300b-1 cwds; legacy_worktree(project, name, unsent=False, at=None) -> absolute path of a real legacy git worktree registered in the temp project, on branch name, placed by default where the old way put it (<parent of project>/worktrees/<name>, outside the Q5 landing root) or at the given path (the only test-side creator of one, exempt in BO-4300f-2's census).

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |

## Risk & Safety

- Touches money? No.
- Touches data? No production data; developer repositories are protected by the ticket 02 session guard.
- Reversibility: all changes are code/docs on the epic branch; nothing ships until the epic PR merges.

## Sign-offs

- [ ] architect-review
- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] ac-validator
- [ ] ac-fulfillment-gate
- [ ] commit

## Comments

_(Append-only log -- leave blank when authoring.)_
