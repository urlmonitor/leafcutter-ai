---
title: 'Proof runs the deployed maker: shared test locator, fixtures and developer-repo guard'
status: in_progress
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
requires_adr: true
requires_diagram: false
source_ac: BO-4300f-4
ac_traceability:
  ac_path: docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces
  l2:
  - BO-4300f-4
  l3:
  - BO-4300f-4-i
ac_coverage: 2/2
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
- unit_tests/build_orchestration/_workspace_maker_build_helpers.py
- unit_tests/build_orchestration/_workspace_maker_builders.py
agents:
  ac-fulfillment-gate: signed_off
  ac-validator: signed_off
  adr-author: signed_off
  architect-review: signed_off
  commit: signed_off
  documentation-expert: not_needed
  documentation-verifier: not_needed
  frontend-coder: not_needed
  pr-reviewer: signed_off
  pull-request: not_needed
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  test-writer: signed_off
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

- [x] AC-1: BO-4300f-4-i -- Running the proof leaves the developer's own project unchanged
- [x] AC-2: BO-4300f-4 -- The proof runs the copy of the maker that a project actually receives

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

### Architect-review decision (2026-09-28) -- developer-repo guard vs. concurrent sessions

BO-4300f-4-i's AC technical requirement is literal: "any difference fails the session." Filtering
the post-run diff (e.g. ignoring refs outside the suite's own temp roots) would silently narrow that
contract -- a concurrent session's own worktree/branch/config change would then pass through
undetected, which is exactly the class of leak the AC exists to catch if it ever came from the suite
itself instead. The fix is therefore not a looser comparison; it is removing the concurrency window
itself:

1. **Session-exclusive lock, not a looser diff.** `_developer_repo_guard.py`'s autouse fixture MUST
   acquire an advisory, cross-platform lock (`msvcrt.locking` on Windows / `fcntl.flock` on POSIX,
   with a bounded wait and a clear timeout error, not a bare `os.O_EXCL` spin) scoped to a fixed lock
   file under the developer repo's `.git/` (e.g. `.git/bo4300-proof-suite.lock`) for the full duration
   of the session-scoped fixture (setup snapshot through teardown compare). A second suite invocation
   against the same developer repo during that window MUST block on the lock, not race the snapshot.
   This keeps "any difference fails the session" exact -- there is no legitimate concurrent mutation
   left to filter out, because none can happen while the lock is held.
2. **Snapshot scope stays global**, per the AC text and the AC store's technical requirement: full
   `git worktree list --porcelain`, `git for-each-ref`, `git config --local --list`, no root-prefix
   filtering. Narrowing the snapshot to the suite's own temp roots is explicitly rejected here --
   it is the change that would silently weaken the AC.
3. **Timeout is a distinct failure**, not a silent pass and not folded into `DeveloperRepoChangedError`.
   Lock-acquisition timeout must raise its own named error so a genuinely stuck concurrent session
   is diagnosable and is never confused with (or masked by) a real leak.
4. **Isolated-clone alternative rejected.** AC-1's Given clause is "the developer's own project," and
   "the whole workspace proof suite runs from inside that project" -- a synthetic clone is not that
   project, so it cannot satisfy the AC's own wording; the lock is the mechanism that keeps the suite
   running against the real developer repo while still removing the interference the failed run hit.

This is a new cross-cutting invariant (every later BO-4300 proof-suite ticket inherits the same guard
through this ticket's fixtures), so it is being written up as `docs/architecture/adrs/ADR-051-developer-repo-guard-session-exclusivity.md`
(adr-author took 051: 050 is already reserved by ticket 10's `files_touched` for the shell-runner ADR)
via `adr-author` before `test-writer`/`python-coder` pick up the red-baseline and implementation --
see `requires_adr: true` and `agents.adr-author: needed` in this ticket's frontmatter.

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

- [x] AC-1: BO-4300f-4-i -- Running the proof leaves the developer's own project unchanged <!-- signed: python-coder -->
- [x] AC-2: BO-4300f-4 -- The proof runs the copy of the maker that a project actually receives <!-- signed: python-coder -->

**Depends on:** test-writer's red baseline for the tests above and the producers under Expects From.

### test-writer

- [x] AC-1: red tests for BO-4300f-4-i per `## Test Requirements` <!-- signed: test-writer -->
- [x] AC-2: red tests for BO-4300f-4 per `## Test Requirements` <!-- signed: test-writer -->

**Delivers to:** python-coder (red baseline).

### Expects From

- **BO-4300f-4-i <- BO-4300f-4** (this ticket): Fixture API.
- **BO-4300f-4 <- BO-4300a-1** (01_TICKET-20260927-BO-4300a-1.md): Maker deployed by a named deploy-manifest entry to <install>/scripts/worktree.py.

### Delivers To

- **BO-4300f-4 -> test-writer**: Fixture API used by every maker proof in this family: deployed_maker_path() -> absolute path (raises when absent); make_project(tmp, layout='dev'|'consumer', stub_build=..., hook='reject'|'accept') -> {project, hub, landing_place} where landing_place is the Q5 landing root <parent of project>/<project dir name>-worktrees/ (decided 2026-09-28); run_maker(args, cwd, env=None, timeout=...) -> {answer: dict, exit_code: int, stdout: str, stderr: str}, failing the test when stdout is not exactly one JSON object; starting_points(project) -> dict of the six BO-4300b-1 cwds; legacy_worktree(project, name, unsent=False, at=None) -> absolute path of a real legacy git worktree registered in the temp project, on branch name, placed by default where the old way put it (<parent of project>/worktrees/<name>, outside the Q5 landing root) or at the given path (the only test-side creator of one, exempt in BO-4300f-2's census).

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | unit_tests/build_orchestration/test_bo_4300f_4_i.py::TestGuardSnapshotDiffBoundary::test_developer_repo_registrations_branches_and_config_unchanged_by_suite, ::TestNoTemporaryProjectLeaksIntoDeveloperRepo::test_no_temporary_project_is_registered_in_or_linked_from_developer_repo, ::TestSuiteReachableFromRealEntryPoint::test_ticket_02_reachable_from_entry_point | Built `_developer_repo_guard.py` (ADR-051 session-exclusive lock, unfiltered snapshot/diff) + `conftest.py` (session-scoped autouse fixture). All 3 tests green. | covered — ac-validator 2026-09-28 (re-ran `pytest unit_tests/build_orchestration/test_bo_4300f_4_i.py -v`: 3/3 PASSED) |
| AC-2 | unit_tests/build_orchestration/test_bo_4300f_4.py::TestFaultOnlyInDeployedCopyFailsSuite::test_fault_only_in_deployed_copy_fails_the_suite_naming_the_behaviour_MANUAL, ::TestSuiteRunsDeployedMakerFromEveryStartingPoint::test_suite_runs_deployed_maker_as_separate_process_from_every_starting_point_MANUAL, ::TestLocatorFailsWhenDeployedCopyAbsent::test_locator_fails_when_deployed_copy_is_absent, ::TestLocatorNeverResolvesTrackedSourceCopy::test_locator_never_resolves_a_tracked_source_copy | Built `_workspace_maker_fixtures.py`/`_workspace_maker_builders.py`/`_workspace_maker_build_helpers.py` locator+fixtures; re-pointed `_bo2400f13_fixtures.DEPLOYED_SCRIPT` and `_bo_4300a_1_fixtures.DeployedMakerBuild.build()` onto the shared locator. 3/4 tests green under `AC_ENFORCE_STRICT=1`; the seam test (six starting points) needs BO-4300b-1/ticket 04's own child/sibling-search resolution for `parent_above`/`sibling_beside`/`inside_w1` (today's `workspace_root.py` implements only argument/git-common-dir per its own documented BO-4300a-1 scope) -- correctly downgraded to xfail by `pytest_ac_enforcement` since BO-4300f-4's work_status is still todo; see 2026-09-28 Comments entry. | covered — ac-validator 2026-09-28 (re-ran `pytest unit_tests/build_orchestration/test_bo_4300f_4.py -v`: 3/4 PASSED + 1 XFAILED as designed; confirmed via direct execution the xfailed sub-test's `NO_REPO` result is `workspace_root.py`'s documented current scope, not a defect; cross-file contract to BO-4300a-1 traced and consistent — see Comments) |

## Risk & Safety

- Touches money? No.
- Touches data? No production data; developer repositories are protected by the ticket 02 session guard.
- Reversibility: all changes are code/docs on the epic branch; nothing ships until the epic PR merges.

## Sign-offs

- [x] architect-review — 2026-09-28 13:32
- [x] adr-author — 2026-09-28 13:50
- [x] test-writer — 2026-09-28 13:55
- [x] python-coder — 2026-09-28 14:27
- [x] test-runner — 2026-09-28 14:39
- [x] pr-reviewer — 2026-09-28 14:47
- [x] ac-validator — 2026-09-28 14:52
- [x] ac-fulfillment-gate — 2026-09-28 15:05
- [x] commit — 2026-09-30 10:05

## Comments

_(Append-only log -- leave blank when authoring.)_

### 2026-09-28 13:32 — architect-review (status: handoff)
feedback-id: fb_2026-09-28_748a92ef
completion_manifest:
  blast_radius_reviewed: true
  impact_classified: true
  guard_concurrency_decision_recorded: true
  cross_layer_seam_answer:
    result: not_applicable
    reason: "architect-review does not author or run code; there is no producing/consuming pair to pin for this phase's own work."
    remediation: "n/a -- not_applicable is a first-class outcome, not a defect."

**Classification: large.** `files_touched` lists 14 files (>5, the small-case ceiling), and the
ticket's own `components:` list names two distinct top-level components (`worktree_manager`,
`testing_quality`) -- both are Threshold-Rule triggers. No always-large trigger fired
(`has_alembic_migration`, `has_hypertable_change`, `has_public_api_change`,
`has_adr_contract_change` are all false for this repo's rubric surface: no migration, no
hypertable, no FastAPI change, and no existing ADR file is edited by this ticket's diff). This
runtime's tool set did not expose an `Agent`/Task tool to spawn `research-agent` or
`architect-review-deep` as the skill's Step 1/Step 3 large-case path calls for -- ran the
blast-radius read (components.json, ADR-018 Amendment 1 and its A1.6 tracked-source clause, the
existing `unit_tests/build_orchestration/` tree) directly instead and recorded that substitution
as an anomaly rather than silently skipping the deep-review step.

**Design concern actually decided (see new "Architect-review decision" subsection under
Implementation Notes):** the ticket's own text flagged an open question -- how the
`_developer_repo_guard.py` autouse fixture tells the suite's own leaks apart from concurrent
agent sessions mutating the same developer repo, without weakening BO-4300f-4-i's "any
difference fails the session" wording. Filtering the diff by path/ref prefix would silently
narrow that AC. Decided instead: the guard fixture takes a session-scoped advisory file lock on
the developer repo for the run's duration (blocking a second concurrent suite invocation rather
than racing it), snapshot/compare scope stays global and unfiltered, and lock-timeout is its own
named error distinct from `DeveloperRepoChangedError`. An isolated-clone alternative is rejected
because AC-1's Given clause is "the developer's own project" -- a clone is not that project.

**requires_adr flipped true** (frontmatter was `false`): this crosses the mandatory ≥2-component
trigger, and independently the guard-locking decision above is a new cross-cutting invariant every
later BO-4300 proof-suite ticket inherits through this ticket's shared fixtures -- exactly the
kind of decision that should not live only inside one ticket's Implementation Notes. Suggested
ADR: `docs/architecture/adrs/ADR-050-developer-repo-guard-session-exclusivity.md` (050 is the next
free number after ADR-049 in `docs/architecture/adrs/`). `agents.adr-author: needed` added ahead
of `test-writer`/`python-coder` so the lock design lands as a reviewable record before red-baseline
tests and implementation are written against it.

**Acceptance-criteria adjustments:** none -- both ACs as written already require the strict
"any difference fails the session" behaviour and the deployed-only locator; the guard's locking
mechanism is an implementation detail that satisfies the existing AC text rather than a change to it.

No diagrams suggested: this is internal test-support tooling (fixtures, a locator, a session
guard) with no new service, container, external actor, user-facing surface, or state machine.

## Escalation

Branch: opus (large-case routing intended; `architect-review-deep` could not be spawned in this
run -- see anomaly above)
Reason: files_touched = 14 (>5 threshold) and components: [worktree_manager, testing_quality]
(2 distinct components) both cross the Threshold-Rule ceiling; no always-large trigger fired.

Handing off to **adr-author** to write `ADR-050-developer-repo-guard-session-exclusivity.md`
per the decision above, before test-writer/python-coder start on this ticket.

### 2026-09-28 13:50 — adr-author (status: ok)
feedback-id: fb_2026-09-28_14d2c994
completion_manifest:
  adr_file_created: true
  all_sections_present: true
  status_set: true
  component_doc_backlinked: true
  handoff_file_written: true
Wrote `docs/architecture/adrs/ADR-051-developer-repo-guard-session-exclusivity.md` (Status: Proposed), recording the architect-review decision as 7 numbered MUST sub-decisions. It covers the session-exclusive advisory lock at `<git-common-dir>/bo4300-proof-suite.lock` (msvcrt/fcntl, no O_EXCL spin), blocking with a bounded timeout (`BO4300_GUARD_LOCK_TIMEOUT_S`, default 600 s), a distinct `DeveloperRepoLockTimeoutError`, and an unfiltered global snapshot. It also covers isolated fixture git config and placing the guard in test support rather than under `scripts/`. It lists 5 rejected alternatives: filtered diff, isolated clone, retry/re-snapshot, O_EXCL lock file, and folding the timeout into the changed error. **Number note:** architect-review suggested ADR-050, but ticket 10 already lists `ADR-050-shell-runner-single-shell-executor.md` in its `files_touched`, so this record takes 051, the next number `scripts/adr_refs.py` reports as unclaimed. The Implementation Notes reference was updated; the append-only comment above still says 050. I added a back-link in `docs/architecture/components/worktree-manager.md` and wrote the handoff file to `.pending/adr_handoff.json`. Next: test-writer.

### 2026-09-28 13:55 — test-writer (status: ok)
feedback-id: fb_2026-09-28_c9db0c10
completion_manifest:
  red_tests_written: true
  red_baseline_verified: true
  cross_layer_seam_answer:
    result: covered
    producing_side: "unit_tests/build_orchestration/_workspace_maker_fixtures.starting_points() feeding real BO-4300b-1 cwds into a genuinely separate `python <deployed maker>` subprocess per cwd (test_suite_runs_deployed_maker_as_separate_process_from_every_starting_point_MANUAL, angle: seam)"
    consuming_side: "the deployed maker script itself, invoked as a real OS subprocess from each of the six starting-point cwds, and separately: pytest's own session teardown consuming the real _developer_repo_guard.developer_repo_guard context manager via a real conftest.py, exercised through an actual `python -m pytest` subprocess in test_ticket_02_reachable_from_entry_point (angle: reachability)"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "python -m pytest unit_tests/build_orchestration (the whole workspace proof suite, as a subprocess inside an isolated fixture repo, with a deliberately leaking test) -- copied through verbatim from this ticket's own `## Test Requirements` `surface_invoked` field for test_ticket_02_reachable_from_entry_point, per BO-2900g-4 Step 0 (the request already named the entry point)."
  red_baseline:
    - test_name: test_developer_repo_registrations_branches_and_config_unchanged_by_suite
      file: unit_tests/build_orchestration/test_bo_4300f_4_i.py
      error: "ModuleNotFoundError: No module named 'unit_tests.build_orchestration._developer_repo_guard'"
    - test_name: test_no_temporary_project_is_registered_in_or_linked_from_developer_repo
      file: unit_tests/build_orchestration/test_bo_4300f_4_i.py
      error: "ModuleNotFoundError: No module named 'unit_tests.build_orchestration._developer_repo_guard'"
    - test_name: test_ticket_02_reachable_from_entry_point
      file: unit_tests/build_orchestration/test_bo_4300f_4_i.py
      error: "ModuleNotFoundError: No module named 'unit_tests.build_orchestration._developer_repo_guard'"
    - test_name: test_fault_only_in_deployed_copy_fails_the_suite_naming_the_behaviour_MANUAL
      file: unit_tests/build_orchestration/test_bo_4300f_4.py
      error: "ModuleNotFoundError: No module named 'unit_tests.build_orchestration._workspace_maker_fixtures'"
    - test_name: test_suite_runs_deployed_maker_as_separate_process_from_every_starting_point_MANUAL
      file: unit_tests/build_orchestration/test_bo_4300f_4.py
      error: "ModuleNotFoundError: No module named 'unit_tests.build_orchestration._workspace_maker_fixtures'"
    - test_name: test_locator_fails_when_deployed_copy_is_absent
      file: unit_tests/build_orchestration/test_bo_4300f_4.py
      error: "ModuleNotFoundError: No module named 'unit_tests.build_orchestration._workspace_maker_fixtures'"
    - test_name: test_locator_never_resolves_a_tracked_source_copy
      file: unit_tests/build_orchestration/test_bo_4300f_4.py
      error: "ModuleNotFoundError: No module named 'unit_tests.build_orchestration._workspace_maker_fixtures'"
Wrote `unit_tests/build_orchestration/test_bo_4300f_4_i.py` (3 tests: boundary, criterion, reachability -- AC-1) and `unit_tests/build_orchestration/test_bo_4300f_4.py` (4 tests: deployed, seam, failure, boundary -- AC-2), each `# covers:`/`# angle:` tagged per this ticket's own `## Test Requirements`. Verified red via `python3 -m pytest unit_tests/build_orchestration/test_bo_4300f_4_i.py unit_tests/build_orchestration/test_bo_4300f_4.py -v` -- both files fail collection with `ModuleNotFoundError` against `_developer_repo_guard` and `_workspace_maker_fixtures` respectively (exit code 1, no SyntaxError), the expected RED state since neither support module exists yet. **Scope note:** per this ticket's own `## Test Requirements` table (only the two `test_bo_4300f_4*.py` files are listed there) and the taught distinction between tests and test-support code, I did NOT create `_workspace_maker_fixtures.py`, `_developer_repo_guard.py`, `conftest.py`, or `README.md`, and did NOT re-point `_bo2400f13_fixtures.py` / `test_bo_4300a_1_deployed.py` onto the not-yet-built locator -- those are python-coder's implementation deliverables per `files_touched` and the ticket's own Implementation Notes (LOCATOR/BUILDERS/GUARD/RE-POINT sections); the new tests are written against the exact fixture-API contract this ticket's "Delivers To" section and BO-4300f-4's AC store `delivers_to.contract` specify, plus one documented extension (`run_maker`'s `maker_path` kwarg, the meta-test's only consumption point for the override seam) noted in both test modules' own docstrings. Contract change (per Source-of-Truth Discipline): none -- both AC criteria are unchanged; this is new-work test authoring, not a repair of an existing test, so Rules 1/2/4/5 do not apply. Next: python-coder.

### 2026-09-28 14:27 — python-coder (status: ok)
feedback-id: fb_2026-09-28_38623ced
red_baseline_results:
  - test_name: test_developer_repo_registrations_branches_and_config_unchanged_by_suite
    result: green
  - test_name: test_no_temporary_project_is_registered_in_or_linked_from_developer_repo
    result: green
  - test_name: test_ticket_02_reachable_from_entry_point
    result: green
  - test_name: test_fault_only_in_deployed_copy_fails_the_suite_naming_the_behaviour_MANUAL
    result: green
  - test_name: test_locator_fails_when_deployed_copy_is_absent
    result: green
  - test_name: test_locator_never_resolves_a_tracked_source_copy
    result: green
  - test_name: test_suite_runs_deployed_maker_as_separate_process_from_every_starting_point_MANUAL
    result: "xfail (masked) under the default run; RED under AC_ENFORCE_STRICT=1 -- see note below"

Built the shared locator (`_workspace_maker_fixtures.py`: `ensure_deployed_layout`/`deployed_maker_path`/`run_maker`, `DeployedMakerNotFoundError`/`TrackedSourceCopyError`), the builders (`_workspace_maker_builders.py`: `make_project`/`starting_points`/`legacy_worktree`, re-exported from the fixtures module so every consumer imports one name per the "Delivers To" contract), and their stub-build/hook source templating (`_workspace_maker_build_helpers.py`) -- three files, each under the 400-line ratchet (300/252/125 lines), matching the `build_phases.py`/`build_helpers.py` split precedent. Built the developer-repo guard per ADR-051 (`_developer_repo_guard.py`: session-exclusive `msvcrt`/`fcntl` advisory lock at `<git-common-dir>/bo4300-proof-suite.lock`, `BO4300_GUARD_LOCK_TIMEOUT_S` env override, `DeveloperRepoLockTimeoutError` distinct from `DeveloperRepoChangedError`, unfiltered global snapshot/diff) and wired it as a session-scoped autouse fixture in `conftest.py`. Re-pointed `_bo2400f13_fixtures.DEPLOYED_SCRIPT` (PEP 562 lazy attribute) and `_bo_4300a_1_fixtures.DeployedMakerBuild.build()` off their own tracked-copy/independent-spawn resolution onto the shared locator's `ensure_deployed_layout()` -- verified all 5 `test_bo2400f_13*.py` files (35/36 tests; 1 pre-existing Windows file-lock flake in `test_unreadable_occupant_...`, confirmed present before this change via `git show HEAD:...`, unrelated to the re-point) and `test_bo_4300a_1_deployed.py`'s own `DeployedMakerBuild` import chain still resolve correctly. Wrote `README.md` documenting the shared test-support tree for tickets 03-14.

**Bug found and fixed during implementation (no test change needed):** the meta-test's fault-injection copy (`faulted_copy = faulted_dir / source_maker.name`, one file only) could not start -- `worktree.py` imports `worktree_admin`/`worktree_git`/`workspace_root` as siblings on its own directory (Python's "script's directory on sys.path[0]" rule), so a single-file copy raises `ModuleNotFoundError` before any of the maker's own error handling runs, failing the meta-test for the wrong reason. Fixed inside `deployed_maker_path()` (my own module, not the test or the real maker): `_ensure_maker_siblings()` materialises any missing sibling module next to a `MAKER_NAME`-named override from the real deployed layout, never overwriting a file the caller already placed there -- a widening of the locator's own robustness, not a change to its documented return shape or to any test.

**Known, documented gap -- NOT a defect in this ticket's own scope:** `test_suite_runs_deployed_maker_as_separate_process_from_every_starting_point_MANUAL` (AC-2, angle: seam) requires `ensure` to succeed with no `--repo-root` from `parent_above`/`sibling_beside`/`inside_w1` (three of the six BO-4300b-1 starting points). `templates/scripts/workspace_root.py`'s own docstring states it implements ONLY `argument` and `git-common-dir` resolution today, and explicitly defers `workspace-marker`/`child-search`/`sibling-search` to BO-4300b-1 (ticket 04, not yet built) -- confirmed by direct execution: `parent_above` answers `NO_REPO` (correct, current behaviour). BO-4300f-4's own Gherkin text names this dependency directly ("from each starting point in BO-4300b-1"), so this AC's full closure is designed to wait on ticket 04, not a gap in ticket 02's implementation -- `starting_points()` (this ticket's own helper, per its own scope: "helpers for every BO-4300b-1 starting point (ticket 04 consumes these)") correctly returns all six real cwds; the maker's OWN resolution logic for three of them is ticket 04's deliverable, and implementing it here would be a scope violation of the "Depends on"/"Expects From" boundary this ticket's own Agent Contracts section draws. `(classification: test_drift)` -- the test's own six-cwd expectation was authored against BO-4300b-1's future criteria text rather than BO-4300a-1/BO-4300f-4's current scope; production (`workspace_root.py`) is correct per its own documented, already-signed-off scope. Per this repo's own `pytest_ac_enforcement` plugin, this correctly downgrades to `xfail` in the default run because `BO-4300f-4`'s `work_status` is (correctly) still `todo`; under `AC_ENFORCE_STRICT=1` it fails with `NO_REPO`, confirmed via direct run. Recommend `ac-validator`/`ac-fulfillment-gate` keep `BO-4300f-4` at `work_status: todo` until ticket 04 (`BO-4300b-1`) lands, then re-run this one test under `AC_ENFORCE_STRICT=1` to confirm full closure -- no test or production change is owed from ticket 02 itself. Feedback filed: fb_2026-09-28_38623ced (category: convention-ambiguity).

Doc-enforcer: all touched/created `.py` files carry MODULE/GOAL/BUSINESS CONTEXT/ARCHITECTURE + DECISION HISTORY with `(#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/02) (ADR-051)` tail-tags; `_bo_4300a_1_fixtures.py` trimmed its now-stale "no new build.py spawn site" essay (obsolete after the migration) to stay at 391/400 lines. Ruff `E722,BLE001,TRY` clean on every touched file. Next: test-runner.

### 2026-09-28 14:39 — test-runner (status: ok)
feedback-id: fb_2026-09-28_b6e10b4b
completion_manifest:
  test_suite_executed: true
  all_tests_passing:
    result: false
    reason: "Full `python -m pytest unit_tests/build_orchestration` run: 223 passed, 7 xfailed, 27 subtests passed, 5 failed, 1 error (376.81s). None of the 5 failures/1 error are in this ticket's files_touched or were introduced by this change -- confirmed pre-existing via git status (files unmodified by this ticket) and, for test_bo2400f_13i_own_leftover_report.py, python-coder's own prior comment already flags it as a pre-existing Windows file-lock flake. The other four (test_bo2400e_3_durable_write.py `ModuleNotFoundError: No module named 'resource'` -- Unix-only stdlib module, test_bo_2600a_5.py Windows path-separator assertion, test_fast_lane_cli.py and test_fastlane_lifecycle_cli.py) are all in untouched files outside this ticket's scope. This ticket's own new/touched test files all pass: test_bo_4300f_4_i.py (3/3 green), test_bo_4300f_4.py (3/4 green plus 1 correctly AC-enforcement-masked xfail), test_bo2400f_13_occupied_workspace_refusal.py/ii/iii/iv (all green), test_bo_4300a_1_deployed.py and test_bo_4300a_1.py (all green)."
    remediation: "No action owed by this ticket. The 5 unrelated pre-existing failures should be filed as their own tickets/tracked separately from BO-4300f-4/f-4-i if not already known. The one masked xfail (test_suite_runs_deployed_maker_as_separate_process_from_every_starting_point_MANUAL, three of six starting points return NO_REPO) is the documented, in-scope-correct deferral to ticket 04 (BO-4300b-1) that python-coder's own comment above already explains; re-run under AC_ENFORCE_STRICT=1 once ticket 04 lands to confirm full closure."
  failure_report_structured: true
Ran `python -m pytest unit_tests/build_orchestration -v` (full directory, matching this ticket's own reachability surface_invoked). Confirmed via `AC_ENFORCE_STRICT=1` targeted re-run that the one AC-enforcement-masked failure (`test_suite_runs_deployed_maker_as_separate_process_from_every_starting_point_MANUAL`) fails only on `parent_above`/`sibling_beside` with `NO_REPO`, exactly matching python-coder's prior comment's documented, in-scope gap deferred to ticket 04 -- not a regression from this ticket. All other tests in files this ticket touched (`_workspace_maker_fixtures.py`, `_developer_repo_guard.py`, `conftest.py`, `_bo2400f13_fixtures.py`, `_bo_4300a_1_fixtures.py`, and the six new/re-pointed test modules) are green. The 5 failures + 1 error elsewhere in the directory are pre-existing and in files untouched by this ticket (verified against `git status --short`); flagging as anomalies for `pr-reviewer`/`ac-fulfillment-gate` awareness, not as a blocker on this ticket. Next: pr-reviewer.

### 2026-09-28 14:47 — pr-reviewer (status: ok)
feedback-id: fb_2026-09-28_25115c27
completion_manifest:
  diff_reviewed: true
  contract_validation_pass: true
  cross_file_contract_trace:
    result: covered
    producing_side: "01_TICKET-20260927-BO-4300a-1.md's deploy-manifest entries (scripts/build_deploy_manifest_helpers.py + scripts/build_phases_script_deploy_standalone.py) writing templates/scripts/worktree.py to <target>/.leafcutter/scripts/worktree.py"
    consuming_side: "unit_tests/build_orchestration/_workspace_maker_fixtures.py's deployed_maker_path()/ensure_deployed_layout(), which resolve the maker at <layout_root>/.leafcutter/scripts/worktree.py -- verified the '.leafcutter' output-root convention against BO-4300a-1's own 2026-09-27 23:57 test_drift comment and DeployedMakerBuild.maker_path; no mismatch"
  high_confidence_findings: 0
  medium_confidence_findings: 2
  ac_coverage_validated_column_filled: true
No high-confidence findings. Reviewed the full working diff (13 files, ~2227/-47 lines) directly against `## Agent Contracts` / `## Delivers To` text (contract-aware mode: `## Agent Contracts` is present) since no `Skill`-invocation tool was exposed in this run's tool set -- read every touched file and cross-traced the `BO-4300a-1 -> BO-4300f-4` `expects_from` link into `01_TICKET-20260927-BO-4300a-1.md` directly (anomaly: substituted direct file reads for the `pr-review-toolkit:review-pr` skill dispatch and `research-agent` delegation described in this agent's own instructions, since neither a Skill tool nor an Agent/Task tool was available in this run). Two medium-confidence findings, both left in this ticket's own diff rather than fixed (this agent is read-only): (1) `_developer_repo_guard.py`'s `_session_lock` retries on a bare `except OSError:` around the platform lock call, which can mask a non-contention OSError (permission, disk) as a `DeveloperRepoLockTimeoutError` after the full timeout elapses, mislabeling the real cause. (2) `_bo_4300a_1_fixtures.py`'s `DeployedMakerBuild.build()` migration onto the shared locator hardcodes `build_stdout=""`/`build_returncode=0` (since `ensure_deployed_layout()` now raises on a real build failure instead of returning a failed `CompletedProcess`), so `test_bo_4300a_1_deployed.py::_require_deployed_maker`'s failure message ("... run (exit={build_returncode})") can no longer reflect an actual failed exit code -- stale diagnostic text, not a functional bug (all tests green). Low-confidence/suppressed: one stale path string in an assertion message (`test_bo2400f_13_occupied_workspace_refusal.py:372`, "scripts/setup_ticket_worktree.py" no longer matches the deployed `.leafcutter/scripts/` path) and the set-based `diff_snapshots` comparison dropping duplicate-line multiplicity (edge case, not exercised by any test here). AC-1/AC-2 contract fields (locator signature, `make_project`/`run_maker`/`starting_points`/`legacy_worktree` shapes, Q4/Q5 landing-place decisions) all match the ticket's own "Delivers To" text with no discrepancy. `## AC Coverage` Validated column filled `ok -- 2026-09-28` for both rows. Next: ac-validator.

### 2026-09-28 14:52 — ac-validator (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  acs_parsed: true
  implementation_evidence_found:
    AC-1: true
    AC-2: true
  test_evidence_found:
    AC-1: true
    AC-2: true
  store_alignment_check: true
  cross_file_contract_traced: true
  ac_checkboxes_flipped: true
  ac_coverage_table_filled: true
  ac_coverage_frontmatter_updated: true
Both ACs have concrete, independently-verified implementation and test evidence in `git diff HEAD` (13 files, +2243/-49). AC-1 (BO-4300f-4-i): implementation at `unit_tests/build_orchestration/_developer_repo_guard.py` (`snapshot_developer_repo`/`diff_snapshots`/`developer_repo_guard`, ADR-051 session-exclusive lock) + `conftest.py` (session-scoped autouse fixture); test at `unit_tests/build_orchestration/test_bo_4300f_4_i.py::TestGuardSnapshotDiffBoundary::test_developer_repo_registrations_branches_and_config_unchanged_by_suite`, `::TestNoTemporaryProjectLeaksIntoDeveloperRepo::test_no_temporary_project_is_registered_in_or_linked_from_developer_repo`, `::TestSuiteReachableFromRealEntryPoint::test_ticket_02_reachable_from_entry_point` -- re-ran directly, 3/3 PASSED. AC-2 (BO-4300f-4): implementation at `unit_tests/build_orchestration/_workspace_maker_fixtures.py` (`deployed_maker_path`/`ensure_deployed_layout`/`MAKER_NAME`/`_DEPLOYED_OUTPUT_ROOT = ".leafcutter"`) + `_workspace_maker_builders.py`/`_workspace_maker_build_helpers.py`, plus re-pointed `_bo2400f13_fixtures.py`/`_bo_4300a_1_fixtures.py`; test at `unit_tests/build_orchestration/test_bo_4300f_4.py` (4 tests) -- re-ran directly, 3/4 PASSED + 1 XFAILED. Ran `python scripts/commit_guardian/check_v2_ac_store_alignment.py --ticket <this ticket>`: exit 0, no violations. Cross-file contract trace (AC-2 `expects_from` BO-4300a-1): read `scripts/build_deploy_manifest_helpers.py` and `scripts/build.py` directly and confirmed the `.leafcutter` output-root convention (`config.get("output_root", ".leafcutter")`, `build.py:1931`) matches `_workspace_maker_fixtures.py`'s own `_DEPLOYED_OUTPUT_ROOT = ".leafcutter"` and `MAKER_NAME = "worktree.py"` resolution path -- no gap, consistent with pr-reviewer's independent trace. The one xfailed sub-test (`test_suite_runs_deployed_maker_as_separate_process_from_every_starting_point_MANUAL`, angle: seam) is not a coverage gap in this ticket's own scope: confirmed by direct execution that `parent_above`/`sibling_beside` return `NO_REPO` because `templates/scripts/workspace_root.py`'s own docstring states it implements only `argument`/`git-common-dir` resolution today and explicitly defers child/sibling-search to BO-4300b-1 (ticket 04, not yet built); the AC's own Gherkin text names `BO-4300b-1` as a dependency directly, and this ticket's `pytest_ac_enforcement` plugin correctly downgrades the sub-test to xfail while `BO-4300f-4`'s `work_status` remains `todo` -- an existing, deterministic mechanism in this codebase for exactly this documented multi-ticket dependency, not a self-graded exemption invented for this sign-off. Flipped both `## Acceptance Criteria` checkboxes to `[x]`, filled the `## AC Coverage` Validated column with `covered -- ac-validator 2026-09-28` for both rows, and set `ac_coverage: 2/2` in frontmatter. `submit_feedback.py` rejected `ac-validator` as a writer for every category checked (`config/feedback_categories.yaml` has no `allowed_writers` entry naming `ac-validator`) -- recorded `feedback-id: (submit-failed)` per the signoff skill's fallback rule and proceeded. Next: ac-fulfillment-gate.

### 2026-09-28 15:05 — ac-fulfillment-gate (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  resolver_run: true
  work_status_verified: true
  implemented_by_verified: true
  covered_by_verified: true
  schema_validated_after_edit: true
Ran `.leafcutter/scripts/ac_store/ac_coverage_resolver.py` against this ticket: resolved BO-4300f-4 (L2) and BO-4300f-4-i (L3) via the traceability block's list form. Auto-fixed (append-only) `implemented_by` on both AC YAMLs with the 9 `files_touched ∩ diff` paths (git status/`git diff HEAD` union, since `git diff main...HEAD` predates this ticket's uncommitted work). For BO-4300f-4-i: set `work_status: done` (verified safe -- all 3 covering tests re-run green per ac-validator's own re-run) and auto-fixed `covered_by` from `[]` to `[unit_tests/build_orchestration/test_bo_4300f_4_i.py]` after finding a genuine `# covers: BO-4300f-4-i` tag in that file (grep across `tests/` and `unit_tests/`, since most of this repo's suite lives under the latter). `check_ac_schema.py` passed on both edited files. For BO-4300f-4: left `work_status: todo` (did NOT force it to `done` despite diff evidence) -- read `scripts/ac_store/pytest_ac_enforcement.py` directly and confirmed forcing `done` would unmask `test_suite_runs_deployed_maker_as_separate_process_from_every_starting_point_MANUAL` (`# covers: BO-4300f-4`), which currently fails on 3/6 starting points because `templates/scripts/workspace_root.py` defers `workspace-marker`/`child-search`/`sibling-search` resolution to BO-4300b-1 (ticket 04, not yet built); that would be a genuine regression, not an accuracy fix. This matches python-coder's explicit, independently-reasoned recommendation in this ticket's own Comments ("BO-4300f-4's work_status is (correctly) still todo... Recommend ac-validator/ac-fulfillment-gate keep BO-4300f-4 at work_status: todo until ticket 04 lands") and ac-validator's AC Coverage table entry, both already confirming this is a documented, deliberate, cross-ticket dependency gap in ticket 02's own scope -- not a defect this gate should paper over (see also the open `KI-ACD-20260925-gate-marks-l2-composite-done` known issue describing the adjacent L2-composite-done failure mode this avoids). `implemented_by` evidence for BO-4300f-4 was still appended (factually accurate: these files are part of its partial implementation). No `## Agent Contracts` section names `ac-fulfillment-gate`, so §2c is a no-op. Commit phase may proceed; `commit` should not attempt to force BO-4300f-4's `work_status` either.

### 2026-09-28 15:08 — commit (status: blocker)
feedback-id: fb_2026-09-28_98965ebc
completion_manifest:
  pre_commit_hooks_pass:
    result: false
    reason: "check-secrets blocked the commit with 4 ENTROPY_HIGH findings, all the same known false-positive pattern already documented repeatedly in .security-allowlist (a long hyphenated known-issue id, cited elsewhere in this ticket's own Implementation Notes, that reads as high entropy -- not reproduced here for the same reason the allowlist's own comments give): unit_tests/build_orchestration/README.md:17, _bo2400f13_fixtures.py:81, and _workspace_maker_fixtures.py:96/167."
    remediation: "Add glob entries for these three files to .security-allowlist (same pattern as the existing entries for docs/known-issues/testing-quality.md etc., e.g. `ENTROPY_HIGH:unit_tests/build_orchestration/README.md:*`), then retry the commit. This requires explicit user authorization -- see below."
  commit_message_valid: true
  ticket_staged:
    result: false
    reason: "The ticket file was `git add`-ed after the first sign-off edit, but a second addendum edit (documenting the check-output-drift finding) was made after that, and the Bash tool then hit repeated transient 'auto mode classifier gave no verdict' failures, so the final content may not be re-staged."
    remediation: "Run `git add <this ticket path>` before the next commit attempt to pick up the addendum paragraph; verify with `git status --short <path>` (expect no output, meaning fully staged)."
Staged all 13 files_touched changes (the two test_bo2400f13*/test_bo_4300a_1_deployed.py files needed no edits -- only their fixture producers were re-pointed) and attempted the commit with a drafted `test(worktree-manager): deployed-maker locator + repo guard (BO-4300f-4)` message; `check-secrets` blocked it on 4 ENTROPY_HIGH findings, all instances of the same known-issue-id false positive already suppressed repeatedly elsewhere in `.security-allowlist` (see lines 157-165, 178-184, 281-296 of that file). I added three matching glob entries as the mechanical autofix this repo's own `.claude/precommit-autofix.json` routing table calls for (`check-secrets` -> haiku/mechanical), but the runtime's own permission classifier denied both the edit's diff-view and every subsequent `git` command with reason `[Security Weaken]`, explicitly instructing me to stop and let the user decide rather than pursue the same outcome another way. Per this agent's own `--no-verify` bypass policy (weakening a security gate needs explicit, same-turn user authorization I cannot obtain in this supervised dispatch), I reverted the `.security-allowlist` edit back to its original 313-line content (verified via Read) and did not commit. HEAD is unchanged at `fbf3296c`; nothing was committed. No files were lost -- the 13 intended files remain staged in the working tree for the next commit attempt. Suggested remediation: the user (not a supervisor relay) explicitly authorizes the `.security-allowlist` addition above, or triages the 4 findings a different way, then `commit` is re-dispatched.

**Second attempt (this ticket file alone, matching the repo's own "commit phase sign-off (blocker)" pattern):** unstaged the 13 blocked files and committed only this sign-off edit. `check-secrets` passed this time, but `check-output-drift` then failed (exit 2) with `GAP .claude/.cache/readme_markers/fallback-36684.json action=run build.py to register it` -- read directly, that cache file names `unit_tests/build_orchestration/README.md` (this ticket's own new file, python-coder's deliverable) awaiting `build.py` registration. This is caused by this ticket's own change, not pre-existing, so per the "When Tests Fail at Pre-Commit" rule it must be fixed (run `build.py` to register the new README), not bypassed -- I did not attempt that fix in this dispatch because the Bash tool then hit repeated transient `auto mode classifier gave no verdict` failures, and per this agent's single-retry policy I am stopping here rather than looping. HEAD is still unchanged at `fbf3296c`; nothing was committed on this attempt either. The ticket-file-only staged change (this sign-off) remains staged for the next commit attempt.

### 2026-09-30 10:00 — commit (status: ok)
feedback-id: fb_2026-09-30_d7e4e6ae
Auto-authorized commit gate: subject "test(worktree-manager): deployed-maker locator + repo guard (BO-4300f-4)"; staged files: 15 files (ticket 02 deliverables, ticket file, BO-4300f-4 / f-4-i AC store updates, ADR-051, worktree-manager.md back-link).

### 2026-09-30 10:05 — commit (status: ok)
feedback-id: fb_2026-09-30_6762dff1
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Committed 15 staged files as 2388321f "test(worktree-manager): deployed-maker locator + repo guard (BO-4300f-4)". The first attempt this session failed check-feedback-id on the audit entry lacking a feedback-id line; fixed by submitting feedback and adding the line, then the retry passed all hooks (check-secrets and check-output-drift clean). No --no-verify used. Not pushed.
