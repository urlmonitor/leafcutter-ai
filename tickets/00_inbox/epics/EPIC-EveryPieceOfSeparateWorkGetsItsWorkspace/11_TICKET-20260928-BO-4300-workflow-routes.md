---
title: 'Every route gets its location only from the maker: confirmed hand-ins, scratch copies, cut-over
  of routes'
status: todo
components:
- build_orchestration
- worktree_manager
created: '2026-09-28'
last_updated: '2026-09-28'
depends_on:
- 08_TICKET-20260928-BO-4300-locate-and-clear.md
- 10_TICKET-20260928-BO-4300-workflow-runtime-and-shell-runner.md
priority: critical
roadmap_phase: phase_1
advances_current_outcome: true
change_target: pipeline
risk_surface: safety
complexity: high
requires_adr: false
requires_diagram: false
source_ac: BO-4300f-1
ac_traceability:
  ac_path: docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces
  l2:
  - BO-4300c-4
  - BO-4300e-4
  - BO-4300f-1
  l3:
  - BO-4300c-4-i
  - BO-4300c-4-ii
ac_coverage: 0/5
tags:
- BO-4300
- re-cut-2026-09-28
files_touched:
- templates/workflows-js/build-epic.js
- templates/workflows-js/build-feature.js
- templates/workflows-js/build-ticket.js
- templates/workflows-js/fast-lane-ship.js
- templates/workflows-js/finalize-feature.js
- templates/workflows-js/plan-feature.js
- templates/workflows-js/quick-fix.js
- templates/workflows/build-backlog.md
- unit_tests/_workflow_engine_harness.py
- unit_tests/build_orchestration/test_bo_4300c_4.py
- unit_tests/build_orchestration/test_bo_4300c_4_i.py
- unit_tests/build_orchestration/test_bo_4300c_4_ii.py
- unit_tests/build_orchestration/test_bo_4300e_4.py
- unit_tests/build_orchestration/test_bo_4300f_1.py
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

# 11: Every route gets its location only from the maker: confirmed hand-ins, scratch copies, cut-over of routes

## Actor / Goal

In order that every route works in the workspace the maker made and nowhere else, we need workflows to take the location only from an ok answer, confirm any handed-in location with the maker, obtain and always clear finalize's comparison copy through the maker, and migrate every remaining route, so that the main copy is exactly as it was after a whole run.

## Context

c-4 expects the WORKSPACE-ANSWER predicate (ticket 10); c-4-i expects locate/verify (e-1, ticket 08); e-4 expects remove (e-2, ticket 08) and scratch readiness 'n/a' (c-1-ii, ticket 05); f-1 expects a-1-ia (ticket 10) and a-1-ib (ticket 09).

Part of `EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace`, re-cut on 2026-09-28 by deliverable (see Master_Plan.md, 'Re-cut 2026-09-28'). This ticket owns the files in `files_touched` and covers 5 AC(s); the AC YAML records under `docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/` are the source of truth and win over any text here.

## AC References

| # | AC | Level | Title | Expects from | Producing ticket |
|---|----|-------|-------|--------------|------------------|
| AC-1 | BO-4300c-4-i | L3 | A location handed in by a caller is confirmed with the maker before any step runs | BO-4300e-1 | 08_TICKET-20260928-BO-4300-locate-and-clear.md |
| AC-2 | BO-4300c-4-ii | L3 | After a whole run, the main copy is exactly as it was | BO-4300c-4 | this ticket |
| AC-3 | BO-4300c-4 | L2 | The workspace location comes only from the maker's ready answer | BO-4300c-2 | 03_TICKET-20260928-BO-4300-answer-contract.md |
| AC-4 | BO-4300e-4 | L2 | Temporary comparison workspaces come and go through the same maker and leave nothing behind | BO-4300e-2 | 08_TICKET-20260928-BO-4300-locate-and-clear.md |
| AC-5 | BO-4300f-1 | L2 | Every existing route now gets its workspace from the one maker | BO-4300a-1-ia, BO-4300a-1-ib | 09_TICKET-20260928-BO-4300-entry-skills.md, 10_TICKET-20260928-BO-4300-workflow-runtime-and-shell-runner.md |

**Closure order.** Children are listed before their parents. Composite(s) `BO-4300c-4` close only after every child listed in their `covered_by` is done (`check-done-proof`); all of those children are in this ticket, so no parent here waits on another ticket. `source_ac` (`BO-4300f-1`) is the anchor `check-ticket-ac-status-parity` checks; `ac_traceability` (list form) names every AC so `ac-fulfillment-gate` verifies each one before commit. The ticket may be set `done` only when every AC above is `work_status: done`.

## Acceptance Criteria

### AC-1: BO-4300c-4-i (L3) -- A location handed in by a caller is confirmed with the maker before any step runs

```gherkin
Given a workflow is started with a workspace location supplied by whoever
  started it,
When the workflow begins,
Then it asks the workspace maker whether that location is a ready workspace for
  this work before any authoring, phase or delivery step runs,
And when the maker does not confirm it, the workflow ends with a failure naming
  the location it was given,
And when the maker confirms it, the workflow proceeds in that location.
```

### AC-2: BO-4300c-4-ii (L3) -- After a whole run, the main copy is exactly as it was

```gherkin
Given the requirements-authoring session, including its product-truth phase, and
  the long-running build each run to completion with a ready workspace,
When the main copy's working files and its branches are compared before and
  after each run,
Then they are identical,
And every file each run produced is inside its workspace.
```

### AC-3: BO-4300c-4 (L2) -- The workspace location comes only from the maker's ready answer

```gherkin
Given a ready answer naming location L, relayed by an agent that also states in
  its own words that the workspace is at a different location M,
When the workflow proceeds,
Then every step it dispatches is directed to work in L,
And the contents of M are identical before and after the run,
And given a ready answer that carries no location, the workflow ends with a
  failure instead of using any other location.
```

### AC-4: BO-4300e-4 (L2) -- Temporary comparison workspaces come and go through the same maker and leave nothing behind

```gherkin
Given finalizing a feature needs a temporary copy of the shared main line to
  run a before-and-after comparison,
When it obtains that copy and later clears it, once with the comparison
  succeeding and once with the comparison failing part-way,
Then in both cases the copy was started from the shared main line tip as read
  after fetching,
And in both cases, afterwards, no folder of the copy remains and the project's
  branches, registered workspaces and settings are identical to before,
And in both cases the clearing is reported in finalize's own result.
```

### AC-5: BO-4300f-1 (L2) -- Every existing route now gets its workspace from the one maker

```gherkin
Given each existing route that works in a workspace -- the long-running build
  for an epic and for a single ticket, the single-ticket build skill, the quick
  fix, requirements authoring, the fast lane, finalize's comparison copies, the
  backlog build, and a person following the project's written instructions --
  is run against a real test project with a real shared project,
When each route obtains its workspace,
Then the workspace it works in carries the one workspace maker's record of
  having made it, and that record agrees with the answer the maker gave,
And no route works in a workspace the maker did not make.
```

- [ ] AC-1: BO-4300c-4-i -- A location handed in by a caller is confirmed with the maker before any step runs
- [ ] AC-2: BO-4300c-4-ii -- After a whole run, the main copy is exactly as it was
- [ ] AC-3: BO-4300c-4 -- The workspace location comes only from the maker's ready answer
- [ ] AC-4: BO-4300e-4 -- Temporary comparison workspaces come and go through the same maker and leave nothing behind
- [ ] AC-5: BO-4300f-1 -- Every existing route now gets its workspace from the one maker

## Test Requirements

Taken from each AC's `test_spec` (one test module per AC); the last entry is the ticket's reachability proof. Every test carries `# covers: <AC-ID>` and `# angle: <angle>`.

```yaml
tests:
- name: test_supplied_location_is_verified_before_any_working_step
  file: unit_tests/build_orchestration/test_bo_4300c_4_i.py
  covers:
  - BO-4300c-4-i
  asserts: The first recorded dispatch after start is the verify request for the supplied location.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
  - templates/workflows-js/plan-feature.js
- name: test_unconfirmed_location_ends_the_run_naming_it
  file: unit_tests/build_orchestration/test_bo_4300c_4_i.py
  covers:
  - BO-4300c-4-i
  asserts: A verify answer of NOT_FOUND/INCOMPLETE ends the run with status error naming the location.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
  - templates/workflows-js/plan-feature.js
- name: test_confirmed_location_is_used_for_later_steps
  file: unit_tests/build_orchestration/test_bo_4300c_4_i.py
  covers:
  - BO-4300c-4-i
  asserts: With an ok verify answer, later dispatches name that location.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
  - templates/workflows-js/plan-feature.js
- name: test_main_copy_identical_after_full_plan_feature_run_including_product_truth
  file: unit_tests/build_orchestration/test_bo_4300c_4_ii.py
  covers:
  - BO-4300c-4-ii
  asserts: Working files and branches of the temporary main copy are identical before and after a complete
    plan-feature run with a ready workspace.
  framework: unittest
  type: behavioral
  angle: real_artifact
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
  - templates/workflows-js/plan-feature.js
- name: test_main_copy_identical_after_full_build_feature_run
  file: unit_tests/build_orchestration/test_bo_4300c_4_ii.py
  covers:
  - BO-4300c-4-ii
  asserts: Same for a complete build-feature run.
  framework: unittest
  type: behavioral
  angle: real_artifact
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
  - templates/workflows-js/plan-feature.js
- name: test_every_file_produced_lies_inside_the_workspace
  file: unit_tests/build_orchestration/test_bo_4300c_4_ii.py
  covers:
  - BO-4300c-4-ii
  asserts: Every file the stubbed writers created is under the workspace_path.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
  - templates/workflows-js/plan-feature.js
- name: test_every_dispatch_uses_location_from_answer_not_agent_prose
  file: unit_tests/build_orchestration/test_bo_4300c_4.py
  covers:
  - BO-4300c-4
  asserts: With an ok answer naming L and relaying prose claiming M, every recorded later dispatch names
    L and none names M.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
  - templates/workflows-js/plan-feature.js
- name: test_location_named_only_in_prose_is_left_untouched
  file: unit_tests/build_orchestration/test_bo_4300c_4.py
  covers:
  - BO-4300c-4
  asserts: Folder M (a real temp folder) is identical before and after the run.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
  - templates/workflows-js/plan-feature.js
- name: test_ok_answer_without_location_ends_the_run
  file: unit_tests/build_orchestration/test_bo_4300c_4.py
  covers:
  - BO-4300c-4
  asserts: An ok answer lacking workspace_path ends the run with status error and no later dispatch.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
  - templates/workflows-js/plan-feature.js
- name: test_scratch_copy_starts_at_hub_main_after_fetch_on_success_and_failure
  file: unit_tests/build_orchestration/test_bo_4300e_4.py
  covers:
  - BO-4300e-4
  asserts: In both runs the scratch answer's base_commit equals the hub's main tip after a new commit
    was pushed to the hub before the run.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
  - templates/workflows-js/plan-feature.js
- name: test_no_scratch_folder_or_registration_remains_after_either_run
  file: unit_tests/build_orchestration/test_bo_4300e_4.py
  covers:
  - BO-4300e-4
  asserts: After both runs the landing place has no scratch entry and the main project's branches, registered
    worktrees and config are identical.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
  - templates/workflows-js/plan-feature.js
- name: test_failure_part_way_still_clears_the_scratch_copy
  file: unit_tests/build_orchestration/test_bo_4300e_4.py
  covers:
  - BO-4300e-4
  asserts: With the comparison scripted to fail part-way, the recorded dispatches still include the remove
    request and it succeeded.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
  - templates/workflows-js/plan-feature.js
- name: test_finalize_result_reports_the_clearing
  file: unit_tests/build_orchestration/test_bo_4300e_4.py
  covers:
  - BO-4300e-4
  asserts: finalize's own result carries the remove outcome in both runs.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
  - templates/workflows-js/plan-feature.js
- name: test_scratch_answer_reports_every_protection_stage_as_na
  file: unit_tests/build_orchestration/test_bo_4300e_4.py
  covers:
  - BO-4300e-4
  asserts: With a fixture project declaring pre-commit, commit-msg and post-merge, the deployed maker's
    ensure --kind scratch answer is ok with hooks_pre_commit_fired, hooks_commit_msg_fired, hooks_post_merge_fired
    and hooks_canary_rejected all 'n/a', while base_is_fresh, is_independent_repo and build_ok are true.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
  - templates/workflows-js/plan-feature.js
- name: test_every_route_works_in_a_workspace_carrying_the_makers_marker
  file: unit_tests/build_orchestration/test_bo_4300f_1.py
  covers:
  - BO-4300f-1
  asserts: For each route (epic and single-ticket build, build-single-ticket skill, quick fix, requirements
    authoring, fast lane, finalize comparison copy, backlog build, written instructions), the workspace
    the route's later steps name holds a ready marker whose fields equal the maker's answer.
  framework: unittest
  type: behavioral
  angle: reachability
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
  - templates/workflows-js/plan-feature.js
- name: test_no_route_works_in_a_workspace_the_maker_did_not_make
  file: unit_tests/build_orchestration/test_bo_4300f_1.py
  covers:
  - BO-4300f-1
  asserts: No route's later dispatches name a location lacking the maker's marker.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
  - templates/workflows-js/plan-feature.js
- name: test_ticket_11_reachable_from_entry_point
  file: unit_tests/build_orchestration/test_bo_4300c_4_i.py
  covers:
  - BO-4300f-1
  angle: reachability
  surface_invoked: each deployed workflow run through unit_tests/_workflow_engine_harness.py with the
    shell stand-in executing the maker for real against a temp project with a bare hub (workflow dispatch)
  asserts: Invoke the production entry point named in surface_invoked (never an import of the function)
    and assert the new behaviour occurs and is consumed.
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
  - templates/workflows-js/plan-feature.js
```

## Implementation Notes

### Ticket-specific (harvested from the failed run and the AC records)

- LOCATION (c-4): the only source of a working location is `workspace_path` of an ok answer; prose from the relaying agent is ignored; retire fast-lane-ship's `gitReportedPath || claimedWorktreePath` fallback and its second git verification; every later dispatch names that location.
- HAND-IN (c-4-i): `args.worktree_path`/`args.workspace_path` is confirmed by one verbatim `worktree.py verify --path <L>` (via the ticket 10 helper and shell-runner) before any working step; retires build-ticket.js's 'trust it' path.
- MAIN COPY (c-4-ii): every write-capable dispatch of plan-feature (incl. the product-truth phase, KI-ACD-007) and build-feature names the workspace as working location and target root; proof snapshots a real temp main copy around a whole harness run.
- SCRATCH (e-4): finalize obtains its comparison copy with `ensure --kind scratch` and always clears it with `remove` on success and failure; the clearing result is part of finalize's result; nothing is registered in the real project.
- ROUTES (f-1): migrate in the migration plan's order (plan-feature -> fast-lane-ship -> build-feature/build-ticket (locate then ensure) -> finalize -> quick-fix) and `templates/workflows/build-backlog.md`; build-feature stops dispatching `worktree_repo_facts.py` (deleted in ticket 14). Retire finalize's branch-substring match (BO-4300a-2). The harness's shell-agent stand-in executes the verbatim maker command for real (extend the harness for this). Neighbour promises (BO-1500f, ACD-2100a, FIN-100g, BP-600f, BO-2400e) stay green or are re-pointed, never deleted.
- COMPANION WORK not in this ticket: skills/commands (ticket 09), worktree-agent charter and `templates/workflows/close-worktree.md`/`worktree.md` (ticket 14, BO-4300f-2-ia).
- EXISTING TESTS: re-pointing workflow tests broken by the route migration follows the same rule as ticket 10 (run the suites, get files_touched extended with the exact list, never delete or skip).
- Commits in workflow prompts go through the commit agent, never `git -C <path> commit`.

### AC technical requirements (verbatim from the AC store; shared boilerplate omitted)

**BO-4300c-4-i**

- A location supplied by the starter (args.worktree_path / args.workspace_path) is confirmed by one verbatim `worktree.py verify --path <L>` (or locate) request before any working step; only an ok answer whose workspace_path equals L (path-equivalence, both spellings) lets the run proceed. Retires build-ticket.js's 'trust it -- no ambient check'.

**BO-4300c-4-ii**

- Every write-capable dispatch of plan-feature (including its product-truth phase, KI-ACD-007) and of build-feature names the workspace as its working location and target root; no path is built from the session cwd.
- Proof: a real temporary main copy is snapshotted (working files and refs) around a complete harness run in which each stubbed writer performs its write at the location its dispatch names; the unit layer cannot run real authoring agents, so the proof is that the location reaching every writer comes from the ok answer (CLAUDE.md: results 'consumed in control flow').

**BO-4300c-4**

- The only source of a working location is workspace_path of an ok answer; prose from the relaying agent is ignored for location purposes (retires fast-lane-ship's claimed-path fallback and the verify-reply trust).
- Every later dispatch names that location as its working location; an ok answer without workspace_path is treated as a failure.
- Every workflow applies ONE acceptance predicate to the maker's answer: it parses as a single JSON object AND status == 'ok' AND workspace_path is a non-empty string; anything else ends the run with status error, quoting (bounded to 2 KB) what was received. The predicate is the one in the build-inlined WORKSPACE-ANSWER block delivered by BO-4300c-3 (byte-identical in every consuming workflow, parity-tested); no workflow hand-copies or re-implements it.

**BO-4300e-4**

- finalize obtains its comparison copy with `ensure --kind scratch` (a detached clone at origin/main after a fetch, landing in the one landing place) and always clears it with `remove` on both the success and the failure path; the clearing result is part of finalize's own result. Nothing is ever registered in the real project (F14); /tmp baselines and `git worktree add --detach` are retired.
- SCRATCH READINESS (decided by the user at the final gate, 2026-09-25): a detached clone has no line of work and nothing is ever committed or merged in it, so the branch ingredients AND every protection-stage canary are reported 'n/a' for kind scratch: hooks_pre_commit_fired, hooks_commit_msg_fired, hooks_post_merge_fired and their conjunction hooks_canary_rejected (confirmed 2026-09-25: the rule covers all three stages of BO-4300c-1-ii, because each stage's canary is a commit or a merge and a comparison copy has neither). The fresh-base, independent-copy and build ingredients still apply. 'n/a' is reported explicitly; no ingredient is silently skipped. No other kind may report hooks_pre_commit_fired or hooks_canary_rejected as 'n/a'; for other kinds the commit-msg and post-merge checks may be 'n/a' only when the project does not declare that stage (BO-4300c-2).

**BO-4300f-1**

- Migrate the workflow bodies to the one maker in the migration plan's recommended order (incident path first): plan-feature.js (ensure --kind ac), fast-lane-ship.js (ensure --kind fastlane; drop its second git verification and the claimed-path fallback), build-feature.js and build-ticket.js (locate then ensure --kind epic|ticket), build-epic.js, quick-fix.js (ensure --kind feature; delete the two-location script lookup), finalize-feature.js (scratch via BO-4300e-4; teardown via remove with up-front authorisation).
- COMPANION WORK (not this agent's surface): the skill, command, agent-charter and workflow-text routes -- build-single-ticket skill, feature skill, quick-fix skill, worktree-agent.md, templates/workflows/build-backlog.md and close-worktree.md -- are llm-expert work under BO-4300a-1-ib and BO-4300f-2-ia. This AC's proof covers them by executing the command each publishes. BO-4300f-1 cannot be split: BO-4300f is at its 5-child cap.
- Proof: every route is run against a real temporary project with a real hub; for workflow routes the harness's shell-agent stand-in executes the verbatim maker command for real, so the workspace later dispatches name is a real one; for the written-instruction route (how-to / CLAUDE.md) the published command is executed. Each workspace must carry the maker's marker agreeing with the answer.
- The neighbours' promises (BO-1500f, ACD-2100a, FIN-100g, BP-600f, BO-2400e) are unchanged; their existing tests must stay green or be re-pointed at the maker, never deleted to pass.

## Agent Contracts

### python-coder

- [ ] AC-1: BO-4300c-4-i -- A location handed in by a caller is confirmed with the maker before any step runs
- [ ] AC-2: BO-4300c-4-ii -- After a whole run, the main copy is exactly as it was
- [ ] AC-3: BO-4300c-4 -- The workspace location comes only from the maker's ready answer
- [ ] AC-4: BO-4300e-4 -- Temporary comparison workspaces come and go through the same maker and leave nothing behind
- [ ] AC-5: BO-4300f-1 -- Every existing route now gets its workspace from the one maker

**Depends on:** test-writer's red baseline for the tests above and the producers under Expects From.

### test-writer

- [ ] AC-1: red tests for BO-4300c-4-i per `## Test Requirements`
- [ ] AC-2: red tests for BO-4300c-4-ii per `## Test Requirements`
- [ ] AC-3: red tests for BO-4300c-4 per `## Test Requirements`
- [ ] AC-4: red tests for BO-4300e-4 per `## Test Requirements`
- [ ] AC-5: red tests for BO-4300f-1 per `## Test Requirements`

**Delivers to:** python-coder (red baseline).

### Expects From

- **BO-4300c-4-i <- BO-4300e-1** (08_TICKET-20260928-BO-4300-locate-and-clear.md): locate/verify read-only answers: ok with workspace_path for a ready workspace; NOT_FOUND or INCOMPLETE otherwise, never with workspace_path.
- **BO-4300c-4-ii <- BO-4300c-4** (this ticket): Location taken only from the ok answer.
- **BO-4300c-4 <- BO-4300c-2** (03_TICKET-20260928-BO-4300-answer-contract.md): The maker's JSON answer per BO-4300c-2: halt unless status == 'ok' and workspace_path is a non-empty string; take the location only from workspace_path (worktree_path is its alias).
- **BO-4300e-4 <- BO-4300e-2** (08_TICKET-20260928-BO-4300-locate-and-clear.md): remove answers (ok with removed_path, or a refusal) consumed by finalize.
- **BO-4300f-1 <- BO-4300a-1-ia** (10_TICKET-20260928-BO-4300-workflow-runtime-and-shell-runner.md): Workflow bodies consume args.workspace or issue one verbatim dispatch.
- **BO-4300f-1 <- BO-4300a-1-ib** (09_TICKET-20260928-BO-4300-entry-skills.md): Entry skills and the workspace skill run the maker and pass args.workspace.

### Delivers To

- consumed by **BO-4300f-2** in 14_TICKET-20260928-BO-4300-retire-former-ways.md

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |

## Risk & Safety

- Touches money? No.
- Touches data? Yes -- workspaces can hold unsent work; every destructive path refuses unless authorised, and proofs run only in temp repos.
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
