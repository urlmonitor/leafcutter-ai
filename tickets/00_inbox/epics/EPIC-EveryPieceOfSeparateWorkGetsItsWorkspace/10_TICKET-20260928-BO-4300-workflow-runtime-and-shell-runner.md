---
title: 'Workflow runtime: one WORKSPACE-ANSWER block, one shell-runner agent, refusals end the run'
status: todo
components:
- build_orchestration
- worktree_manager
- agent_registry
created: '2026-09-28'
last_updated: '2026-09-28'
depends_on:
- 03_TICKET-20260928-BO-4300-answer-contract.md
- 09_TICKET-20260928-BO-4300-entry-skills.md
priority: critical
roadmap_phase: phase_1
advances_current_outcome: true
change_target: pipeline
risk_surface: contract_boundary
complexity: high
requires_adr: true
requires_diagram: false
source_ac: BO-4300c-3
ac_traceability:
  ac_path: docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces
  l2:
  - BO-4300c-3
  l3:
  - BO-4300c-3-i
  - BO-4300c-3-ii
  - BO-4300a-1-ia
ac_coverage: 0/4
tags:
- BO-4300
- re-cut-2026-09-28
files_touched:
- templates/workflows-js/build-epic.js
- templates/workflows-js/build-feature.js
- templates/workflows-js/build-ticket.js
- templates/workflows-js/create-ticket.js
- templates/workflows-js/fast-lane-ship.js
- templates/workflows-js/finalize-feature.js
- templates/workflows-js/plan-feature.js
- templates/workflows-js/quick-fix.js
- templates/workflows-js/_shared/workspace-answer.js
- templates/workflows-js/_shared/README.md
- scripts/build_phases_workflows.py
- unit_tests/_workflow_engine_harness.py
- config/agent_registry.json
- templates/agents/shell-runner.md
- docs/agents/README.md
- docs/agents/utility/shell-runner.md
- docs/architecture/components/agent-registry.md
- docs/architecture/adrs/ADR-050-shell-runner-single-shell-executor.md
- unit_tests/build_orchestration/test_bo_4300a_1_ia.py
- unit_tests/build_orchestration/test_bo_4300a_1_ia_lint.py
- unit_tests/build_orchestration/_bo_4300a_1_ia_fixtures.py
- unit_tests/build_orchestration/test_bo_4300c_3.py
- unit_tests/build_orchestration/test_bo_4300c_3_i.py
- unit_tests/build_orchestration/test_bo_4300c_3_ii.py
agents:
  ac-fulfillment-gate: needed
  ac-validator: needed
  adr-author: needed
  architect-review: needed
  commit: needed
  documentation-expert: needed
  documentation-verifier: needed
  frontend-coder: not_needed
  llm-expert: needed
  pr-reviewer: needed
  pull-request: not_needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  test-writer: needed
  user-surface-smoker: not_needed
---

# 10: Workflow runtime: one WORKSPACE-ANSWER block, one shell-runner agent, refusals end the run

## Actor / Goal

In order that no workflow can build a workspace in its own words or treat a refusal as success, we need one build-inlined WORKSPACE-ANSWER block, one narrow shell-running agent that every shell step goes to, and a runtime rule that a decline/prose/result-less reply ends the run quoting it, so that the 2026-09-25 incident path is structurally closed in every workflow.

## Context

a-1-ia needs the WORKSPACE-ANSWER block (c-3), the result schema (c-2, ticket 03) and `args.workspace` (a-1-ib, ticket 09); in the failed run ticket 02 was scheduled before all three and blocked. The repo-wide shell-dispatch lint went red on 17 dispatches across the 8 workflows (02 test-writer), and python-coder refused to grant `permits_shell` to existing agents because each grant is a charter change (02 python-coder, architect-review). User decision 2026-09-28 (b): ONE new narrow agent with `permits_shell: true` that runs one exact command and relays its output verbatim; every shell-running workflow step moves to it; no existing agent's charter changes.

Part of `EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace`, re-cut on 2026-09-28 by deliverable (see Master_Plan.md, 'Re-cut 2026-09-28'). This ticket owns the files in `files_touched` and covers 4 AC(s); the AC YAML records under `docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/` are the source of truth and win over any text here.

## AC References

| # | AC | Level | Title | Expects from | Producing ticket |
|---|----|-------|-------|--------------|------------------|
| AC-1 | BO-4300c-3-i | L3 | Success reported with output that is not a valid answer is a failure, never 'use the current checkout' | BO-4300c-3 | this ticket |
| AC-2 | BO-4300c-3-ii | L3 | An agent that declines the workspace step ends the run, and no other command is substituted | BO-4300c-3 | this ticket |
| AC-3 | BO-4300c-3 | L2 | Every caller stops on anything but a ready answer | BO-4300c-2 | 03_TICKET-20260928-BO-4300-answer-contract.md |
| AC-4 | BO-4300a-1-ia | L3 | No workflow body asks an agent to make a workspace in its own words | BO-4300a-1-ib | 09_TICKET-20260928-BO-4300-entry-skills.md |

**Closure order.** Children are listed before their parents. Composite(s) `BO-4300c-3` close only after every child listed in their `covered_by` is done (`check-done-proof`); all of those children are in this ticket, so no parent here waits on another ticket. `source_ac` (`BO-4300c-3`) is the anchor `check-ticket-ac-status-parity` checks; `ac_traceability` (list form) names every AC so `ac-fulfillment-gate` verifies each one before commit. The ticket may be set `done` only when every AC above is `work_status: done`.

## Acceptance Criteria

### AC-1: BO-4300c-3-i (L3) -- Success reported with output that is not a valid answer is a failure, never 'use the current checkout'

```gherkin
Given the requirements-authoring session is started from the workspace parent
  folder,
And the step meant to obtain its workspace ends reporting success, but its
  output is the file path of a script rather than a valid answer from the
  workspace maker,
When the session receives that result,
Then the session ends with a failure stating that no valid answer was received,
  and quoting the output it got,
And that result is not treated as "no workspace needed" or as "use the current
  checkout",
And the main copy's working files are identical before and after the session,
And the recorded dispatches contain no authoring step.
```

### AC-2: BO-4300c-3-ii (L3) -- An agent that declines the workspace step ends the run, and no other command is substituted

```gherkin
Given the agent asked to obtain the workspace declines, stating that the task is
  outside its role,
When the workflow receives the decline,
Then the workflow ends with a failure that names the decline,
And it does not send a different command in place of the one declined,
And no later step is dispatched.
```

### AC-3: BO-4300c-3 (L2) -- Every caller stops on anything but a ready answer

```gherkin
Given each workflow that needs a workspace -- the long-running build, the
  single-ticket build, the quick fix, the requirements-authoring session, the
  fast lane and finalize -- is run with the workspace maker's answer replaced,
  in turn, by: a refusal; an error; a paragraph of prose; an answer that states
  neither ready nor refused; and no answer at all,
When the workflow receives that answer,
Then it ends with a failure that quotes what it received,
And its recorded dispatches contain no authoring, phase, commit or delivery
  step after the workspace step,
And it does not continue in the main copy, in the epic folder, in the folder it
  was started from, or in any location it was not given in a ready answer.
```

### AC-4: BO-4300a-1-ia (L3) -- No workflow body asks an agent to make a workspace in its own words

```gherkin
Given each workflow that needs a workspace is run with a recording stand-in in
  place of every agent it dispatches,
When the workflow reaches the point where it needs a workspace,
Then it either receives the workspace maker's answer as part of its input, or
  issues exactly one request, which asks for the workspace maker to be run
  unchanged and its answer relayed word for word,
And no dispatched request asks an agent to create, copy, set up, link or
  repair a workspace by steps of the agent's own choosing,
And no workspace request is dispatched to an agent that is not permitted to
  run commands.

Given every workflow the project delivers, and the agents' permissions to run
  shell commands as they stand when the check runs,
When every step of every workflow that asks an agent to run a shell command is
  checked -- including steps that a single run of the workflow does not reach --
Then no such step is sent to an agent that is not permitted to run shell
  commands, and an agent with no stated permission counts as not permitted,
And each offending step is reported by workflow, step, agent and the command it
  asks for,
And a workflow added later, or a change to an agent's permission, is covered
  by the same check without anyone editing a list,
And when an agent asked to run a shell command declines, answers in prose, or
  answers without a result, the workflow ends with an error that quotes the
  answer received, and no later step of that workflow is dispatched -- a
  refusal is never taken as the step having run.
```

- [ ] AC-1: BO-4300c-3-i -- Success reported with output that is not a valid answer is a failure, never 'use the current checkout'
- [ ] AC-2: BO-4300c-3-ii -- An agent that declines the workspace step ends the run, and no other command is substituted
- [ ] AC-3: BO-4300c-3 -- Every caller stops on anything but a ready answer
- [ ] AC-4: BO-4300a-1-ia -- No workflow body asks an agent to make a workspace in its own words

## Test Requirements

Taken from each AC's `test_spec` (one test module per AC); the last entry is the ticket's reachability proof. Every test carries `# covers: <AC-ID>` and `# angle: <angle>`.

```yaml
tests:
- name: test_success_with_script_path_output_ends_plan_feature_in_failure
  file: unit_tests/build_orchestration/test_bo_4300c_3_i.py
  covers:
  - BO-4300c-3-i
  asserts: Started from the workspace parent with a workspace step returning exit 0 and a file path, plan-feature
    ends with status error naming 'no valid answer' and quoting the path.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/create-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
- name: test_invalid_answer_is_not_treated_as_no_workspace_needed
  file: unit_tests/build_orchestration/test_bo_4300c_3_i.py
  covers:
  - BO-4300c-3-i
  asserts: No recorded dispatch runs in the current checkout or omits a workspace location.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/create-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
- name: test_main_copy_working_files_unchanged_after_the_session
  file: unit_tests/build_orchestration/test_bo_4300c_3_i.py
  covers:
  - BO-4300c-3-i
  asserts: The temporary main copy's working files and branches are identical before and after.
  framework: unittest
  type: behavioral
  angle: real_artifact
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/create-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
- name: test_no_authoring_dispatch_is_recorded
  file: unit_tests/build_orchestration/test_bo_4300c_3_i.py
  covers:
  - BO-4300c-3-i
  asserts: The dispatch list contains no product-owner, business-analyst or it-po dispatch.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/create-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
- name: test_declining_workspace_agent_ends_the_run_naming_the_decline
  file: unit_tests/build_orchestration/test_bo_4300c_3_ii.py
  covers:
  - BO-4300c-3-ii
  asserts: With the workspace step scripted to decline, the run ends with status error whose message cites
    the decline.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/create-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
- name: test_no_substitute_command_is_sent_after_a_decline
  file: unit_tests/build_orchestration/test_bo_4300c_3_ii.py
  covers:
  - BO-4300c-3-ii
  asserts: Exactly one workspace dispatch is recorded.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/create-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
- name: test_no_later_step_is_dispatched_after_a_decline
  file: unit_tests/build_orchestration/test_bo_4300c_3_ii.py
  covers:
  - BO-4300c-3-ii
  asserts: The recorded dispatch list ends at the declined step.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/create-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
- name: test_harness_unscripted_dispatch_is_never_a_success
  file: unit_tests/build_orchestration/test_bo_4300c_3_ii.py
  covers:
  - BO-4300c-3-ii
  asserts: A minimal workflow run under the harness with one unscripted dispatch receives an error-shaped
    reply (or the test run fails loudly) and the harness result names the unscripted label; no reply with
    status 'ok' or exit_code 0 is produced for it.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/create-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
- name: test_harness_scripts_refusal_prose_and_non_json_replies
  file: unit_tests/build_orchestration/test_bo_4300c_3_ii.py
  covers:
  - BO-4300c-3-ii
  asserts: A workflow under the harness receives, per scripted label, a decline, a prose paragraph, a
    bare file path with exit 0, and JSON lacking status, each exactly as scripted and not coerced into
    an ok object.
  framework: unittest
  type: behavioral
  angle: seam
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/create-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
- name: test_each_workflow_ends_in_failure_on_each_non_ready_answer
  file: unit_tests/build_orchestration/test_bo_4300c_3.py
  covers:
  - BO-4300c-3
  asserts: Across 6 workflows x 5 answers, every run ends with status error.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/create-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
- name: test_failure_quotes_what_was_received
  file: unit_tests/build_orchestration/test_bo_4300c_3.py
  covers:
  - BO-4300c-3
  asserts: Each failure message contains the received answer (bounded).
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/create-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
- name: test_no_authoring_phase_commit_or_delivery_step_is_dispatched_after_the_workspace_step
  file: unit_tests/build_orchestration/test_bo_4300c_3.py
  covers:
  - BO-4300c-3
  asserts: In every run the recorded dispatch list ends at the workspace step.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/create-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
- name: test_no_run_continues_in_main_copy_epic_folder_start_folder_or_any_ungiven_location
  file: unit_tests/build_orchestration/test_bo_4300c_3.py
  covers:
  - BO-4300c-3
  asserts: No recorded dispatch names a working location other than one taken from an ok answer.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/create-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
- name: test_workspace_answer_block_is_byte_identical_in_every_deployed_consumer
  file: unit_tests/build_orchestration/test_bo_4300c_3.py
  covers:
  - BO-4300c-3
  asserts: For every deployed workflow carrying the WORKSPACE-ANSWER markers, the text between them equals
    the single source block byte for byte; a difference names the workflow.
  framework: unittest
  type: unit
  angle: deployed
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/create-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
- name: test_every_workspace_consuming_workflow_carries_the_block
  file: unit_tests/build_orchestration/test_bo_4300c_3.py
  covers:
  - BO-4300c-3
  asserts: Every deployed workflow that reads args.workspace or records a workspace dispatch carries the
    block; a fixture workflow consuming a workspace without it makes the test fail naming that workflow.
  framework: unittest
  type: unit
  angle: failure
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/create-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
- name: test_build_fails_on_a_hand_filled_block_and_is_idempotent
  file: unit_tests/build_orchestration/test_bo_4300c_3.py
  covers:
  - BO-4300c-3
  asserts: 'Run against a temporary templates tree (never the package''s own build.py as a subprocess):
    the workflow phase fills an empty marker pair from the source, refuses a template whose marker pair
    already holds text, and a second run writes nothing.'
  framework: unittest
  type: behavioral
  angle: seam
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/create-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
- name: test_each_workflow_receives_answer_or_issues_one_verbatim_maker_request
  file: unit_tests/build_orchestration/test_bo_4300a_1_ia.py
  covers:
  - BO-4300a-1-ia
  asserts: Every deployed workflow that needs a workspace, run with recording stand-ins, either consumes
    args.workspace or records exactly one workspace dispatch whose prompt is the exact maker command plus
    a verbatim-relay instruction.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/create-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
- name: test_no_dispatch_asks_an_agent_to_build_a_workspace_by_its_own_steps
  file: unit_tests/build_orchestration/test_bo_4300a_1_ia.py
  covers:
  - BO-4300a-1-ia
  asserts: No recorded dispatch prompt in any workflow run asks an agent to create, copy, set up, link
    or repair a workspace (no clone/worktree/symlink/copy/bootstrap instructions outside the one maker
    command).
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/create-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
- name: test_workspace_requests_only_reach_shell_permitted_agents
  file: unit_tests/build_orchestration/test_bo_4300a_1_ia.py
  covers:
  - BO-4300a-1-ia
  asserts: 'Every recorded workspace dispatch targets an agent whose registry entry has permits_shell:
    true, read from the registry at test time.'
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/create-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
- name: test_every_deployed_workflow_is_covered_without_editing_a_list
  file: unit_tests/build_orchestration/test_bo_4300a_1_ia.py
  covers:
  - BO-4300a-1-ia
  asserts: The workflows exercised are enumerated from the deployed workflow directory, so adding a workflow
    extends the check automatically.
  framework: unittest
  type: behavioral
  angle: seam
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/create-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
- name: test_every_shell_running_dispatch_in_every_workflow_targets_a_shell_permitted_agent
  file: unit_tests/build_orchestration/test_bo_4300a_1_ia_lint.py
  covers:
  - BO-4300a-1-ia
  asserts: 'Repo-wide lint over every templates/workflows-js/*.js: each agent dispatch whose prompt runs
    a shell command names an agentType with permits_shell: true in config/agent_registry.json, read at
    test time (an agent with no permits_shell field counts as not permitted), including dispatch sites
    a single run does not reach; each violation is reported by workflow, step (dispatch label or location),
    agentType and the command the prompt asks for.'
  framework: unittest
  type: unit
  angle: seam
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/create-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
- name: test_shell_dispatch_lint_catches_a_status_checker_git_dispatch
  file: unit_tests/build_orchestration/test_bo_4300a_1_ia_lint.py
  covers:
  - BO-4300a-1-ia
  asserts: Fed a fixture workflow that asks status-checker to run `git reset --hard`, and one that asks
    an agent without a permits_shell field to run a python script, the lint reports both, each report
    naming workflow, step, agent and command; fed the same prompts dispatched to worktree-agent it reports
    neither.
  framework: unittest
  type: unit
  angle: failure
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/create-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
- name: test_refused_non_workspace_shell_step_ends_the_workflow_with_a_quoting_error
  file: unit_tests/build_orchestration/test_bo_4300a_1_ia.py
  covers:
  - BO-4300a-1-ia
  asserts: Through unit_tests/_workflow_engine_harness.py, a deployed workflow is run with a NON-workspace
    shell-running step (e.g. a git or test command) scripted to (a) decline, (b) answer in prose, and
    (c) answer without the requested result; in each case the workflow ends with an error whose text quotes
    the scripted reply, and the recorded dispatch list contains no step after the refused one.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/create-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
- name: test_workspace_dispatch_goes_through_the_shared_block_helper
  file: unit_tests/build_orchestration/test_bo_4300a_1_ia.py
  covers:
  - BO-4300a-1-ia
  asserts: In each deployed workflow run that issues a workspace dispatch, the recorded dispatch's prompt,
    agentType and schema are exactly those the WORKSPACE-ANSWER block's helper produces for the same command.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/create-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
- name: test_ticket_10_reachable_from_entry_point
  file: unit_tests/build_orchestration/test_bo_4300c_3_i.py
  covers:
  - BO-4300c-3
  angle: reachability
  surface_invoked: each deployed .claude/workflows/*.js run through unit_tests/_workflow_engine_harness.py
    run_workflow_under_e2() with label-scripted replies (workflow dispatch)
  asserts: Invoke the production entry point named in surface_invoked (never an import of the function)
    and assert the new behaviour occurs and is consumed.
  implementation_files:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/create-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
```

## Implementation Notes

### Ticket-specific (harvested from the failed run and the AC records)

- SHELL-RUNNER AGENT (deliverable of this ticket; llm-expert authors the charter, python-coder the registry entry): `templates/agents/shell-runner.md`. Contract: input is one exact command line (absolute paths); it runs it once, unchanged, never a compound or substituted command, never decides anything; it returns `{exit_code, stdout, stderr}` verbatim under the dispatch's result schema; it declines anything else. Tools: `Bash` only -- no Edit/Write, so CLAUDE.md's `requires_verification: true` rule does not trigger (if Edit/Write were ever added it would become mandatory; verify with `grep -n "requires_verification\|Edit\|Write" templates/agents/shell-runner.md`). Registry entry in `config/agent_registry.json` with `permits_shell: true`, `is_ticket_phase: false`, `spawned_by` = the workflows, `portable: true`, `components: [build_orchestration]`; row in `docs/agents/README.md`; card at `docs/agents/utility/shell-runner.md` (sibling of worktree-agent's). Follow `templates/skills/add-agent-to-package/SKILL.md` steps 3-6 (registry validation via `build.py --validate-only`). status-checker, worktree-agent and every other agent keep their charters and registry entries unchanged.
- MOVE every workflow step whose prompt runs a shell command (git, gh, python/python3, node/npm, pytest, rm, mv, cp, bash/sh, pwsh) to shell-runner, rewritten as 'run this exact command, relay verbatim'; that includes the workspace dispatch in the WORKSPACE-ANSWER helper. Known offenders (02 test-writer red baseline): build-epic.js/worktree-check -> status-checker/git; fast-lane-ship.js/fastlane-context-bundle -> python-coder/python3; plan-feature.js/detect-current-branch -> status-checker; finalize-feature.js (20 status-checker dispatches) is not reached by a harness run and is covered only by the static lint, so check it against the lint's report, not a run.
- LINT (a-1-ia): one declared, reviewed rule held in one place; workflows enumerated from `templates/workflows-js/*.js`, permissions read from `config/agent_registry.json` at test time (absent `permits_shell` = not permitted); self-check fixture (status-checker `git reset --hard`, an agent without the field running python) must be reported, the same prompts to a permitted agent must not. No dispatch exempted by name.
- BLOCK (c-3): single tracked source `templates/workflows-js/_shared/workspace-answer.js` (not deployed as a workflow by the shallow glob); `scripts/build_phases_workflows.py` fills `// WORKSPACE-ANSWER-START`/`-END` in each consuming template, fails the build when a template's marker pair already holds text or the source is missing, keeps compare-before-write idempotency and runs before config-placeholder injection. Parity test on the DEPLOYED workflows; the consuming set is derived, never listed. The BO-3900 PATH-HELPERS blocks are the marker precedent but are NOT inlined (moving them is out of scope).
- REPLY RULE (a-1-ia, c-3-i, c-3-ii): enforced in ONE shared place in the workflow runtime: a decline, prose, non-JSON, or result-less reply to any shell step ends the run with an error quoting (<= 2 KB) the reply; nothing later is dispatched; no fallback to the current checkout, epic folder or start folder. Remove the F2 'no workspace is normal' fallbacks listed in c-3's it_requirements that concern ACCEPTING the answer (plan-feature null-worktree mode, build-epic callerWorktreePath||probe||epicPath, finalize 'unknown' default). Taking the location only from `workspace_path` (fast-lane-ship claimed path, build-ticket unchecked worktree_path) is ticket 11's c-4.
- HARNESS: extend `unit_tests/_workflow_engine_harness.py` to script hostile replies (decline, prose, exit 0 with non-JSON, JSON without status, no answer) for the workspace step and for any other shell step. Assert on the RECORDED dispatch list of the deployed workflow, never on source text.
- EXISTING TESTS: ~40 test files under `unit_tests/` and `tests/` mention status-checker (e.g. `unit_tests/workflows/test_bo_1500f_1_real_registry_read.py`, `unit_tests/test_build_ticket_workflow.py`, `unit_tests/workflows/test_fin_100h_refusal_not_success.py`). Those that assert the agentType or label of a step this ticket moves must be re-pointed (never deleted, never skipped). They are not pre-listed in files_touched because which ones break is known only after the move: run the full `unit_tests/workflows` and `unit_tests/prompt_assembly` suites after the move, then get this ticket's files_touched extended with the exact list before editing them.
- ADR: record the decision (one narrow shell executor for workflow shell steps; lint as the enforcement; relation to ADR-006 depth rules and ADR-030 E2 no-process-access) as a new ADR. `ADR-050-...` is the expected next free number; adr-author confirms it and, if different, the ticket's files_touched is corrected before writing.
- STARTING POINT (re-verify): `git show refs/wip/bo4300-attempt1:unit_tests/build_orchestration/test_bo_4300a_1_ia.py`, `refs/wip/bo4300-attempt1:unit_tests/build_orchestration/test_bo_4300a_1_ia_lint.py`, `refs/wip/bo4300-attempt1:unit_tests/build_orchestration/_bo_4300a_1_ia_fixtures.py` (at the 400-line ceiling). Its tests discover the block via its markers rather than a function name, so they stay valid wherever the block lands.
- Commits in workflow prompts go through the commit agent, never `git -C <path> commit`.

### AC technical requirements (verbatim from the AC store; shared boilerplate omitted)

**BO-4300c-3-i**

- plan-feature fails when the workspace step reports success with output that is not one JSON object (the incident's script path), quoting the output; the parse failure is never caught into 'no workspace'.
- The main-copy check snapshots a real temporary project's working files and branches around the harness run.

**BO-4300c-3-ii**

- A decline (the agent states the task is outside its role) is a failure naming the decline; the workflow never re-sends a different command, to the same or another agent, in its place (the incident's step 3-4).
- HARNESS DEFAULT (duplication audit C2 item 11, KI-BO-009): unit_tests/_workflow_engine_harness.py's agent() stub today answers any unscripted dispatch with {status: 'ok', exit_code: 0, passed: true, ...}, so a workflow that mishandles a refusal is never exercised. The default must stop being a success: a dispatch with no scripted reply either returns an error-shaped reply (status 'error', naming the unscripted label) or fails the test loudly; in both cases the harness result records the unscripted dispatch so a test can assert on it. A success reply is only ever returned because a test scripted it.
- The harness must be able to script, per label, a refusal (the agent declines as outside its role), a prose paragraph, a non-JSON reply (including exit 0 with a bare file path), and JSON without status -- delivered to the workflow in the shape the real engine delivers them, not pre-parsed into an ok object.
- Blast radius: every existing harness-driven test that relied on the ok default must script its replies explicitly (the existing script-specific defaults in _default_label_responses_for_script / _default_args_for_script are scripted replies and may stay). The ticket for this record lists the tests that changed; no test is skipped or xfailed to absorb the change.

**BO-4300c-3**

- Every workflow applies ONE acceptance predicate to the maker's answer: it parses as a single JSON object AND status == 'ok' AND workspace_path is a non-empty string; anything else ends the run with status error, quoting (bounded to 2 KB) what was received.
- ONE BUILD-INLINED BLOCK, NOT HAND COPIES (duplication audit C3; KI-BO-20260925-finalize-gate-accepts-agent-answers is the hand-copy failure this prevents): the acceptance predicate and the workspace dispatch helper live in ONE marker-delimited block (e.g. `// WORKSPACE-ANSWER-START` / `// WORKSPACE-ANSWER-END`) with a single tracked source outside the deployed workflow set (e.g. templates/workflows-js/_shared/, which the shallow *.js glob in build_workflow_scripts does not deploy as a workflow). Each consuming workflow template carries only the marker pair; the workflow build phase (scripts/build_phases_workflows.py) fills it with the source block, and a template whose marker pair already holds text, or a source block that is missing, fails the build rather than being deployed. E2 bodies still have no require (ADR-030); inlining happens at build time only.
- Precedent, verified 2026-09-25: the BO-3900-PATH-HELPERS-START/END blocks are the marker convention this follows, but they are NOT build-inlined and have NO parity test -- build-feature.js and plan-feature.js carry different text between the same markers today, and unit_tests/portability/_bo3900a_js_classifier.py and unit_tests/workflows/_bo3900e_resolver_harness.py only slice them out for Node execution. This record therefore delivers the build inliner and the parity test; moving the BO-3900 block onto the same mechanism is a follow-up outside this tree.
- Parity and coverage are tested on the DEPLOYED workflows: the block text in every deployed workflow that carries the markers is byte-identical to the source block, and every workflow that consumes a workspace (reads args.workspace, or issues a workspace dispatch in its BO-4300a-1-ia harness run) carries the block. The consuming set is derived, never a hard-coded list.
- The build inliner is a change to the build pipeline (scripts/build_phases_workflows.py) and must keep that phase's compare-before-write idempotency (a second build writes nothing) and run before config-placeholder injection.
- Remove every fallback that treats 'no workspace' as a normal state (F2): plan-feature.js's null-worktree mode and every `authoringWorktreePath ? ... : ...` branch, build-epic.js's callerWorktreePath || probe || epicPath fallback, finalize-feature.js's worktree_root 'unknown' default, fast-lane-ship.js's `gitReportedPath || claimedWorktreePath`, build-ticket.js's unchecked args.worktree_path. Line numbers in the analysis are hints; verify against HEAD.
- The workflows covered are the long-running build, the single-ticket build, quick fix, requirements authoring, the fast lane and finalize; the five hostile answers are a refusal, an error, a paragraph of prose, a JSON object with neither ok nor refused as status, and no answer at all.
- Entry skills that run the maker stop on a non-zero exit (BO-4300a-1-ib); this AC covers the workflow bodies.

**BO-4300a-1-ia**

- Remove every free-form workspace instruction from the workflow bodies: build-feature.js's 'Open a NEW git worktree ... Bootstrap it (copy/symlink .leafcutter ...)' prompt, the resolver and branch-check steps plan-feature.js sends to status-checker, finalize-feature.js's `git worktree add/remove` and `rm -rf` prompts, and fast-lane-ship.js's create prompt. Line numbers in the analysis are hints; verify against HEAD.
- A workspace dispatch's prompt carries only the exact absolute maker command and the instruction to run it unchanged and relay stdout verbatim; the agent's reply is parsed with the BO-4300c-2 schema.
- ONE SHARED DISPATCH HELPER (duplication audit C3/C2): the workspace dispatch is issued only through the dispatch helper in the WORKSPACE-ANSWER block delivered by BO-4300c-3 (build-inlined, byte-identical in every consuming workflow). No workflow builds its own workspace dispatch or its own reply parsing.
- Reply handling applies to EVERY step in every workflow that asks an agent to run a shell command, not only workspace dispatches: the dispatch carries a result schema; a decline, a prose reply, a non-JSON reply, or a reply without the result the step asked for (for the workspace dispatch: JSON without status) is an error that ends the workflow, and the error quotes the reply received. No later step of that workflow is dispatched after such a reply, and a refusal is never taken as the step having run. For the workspace dispatch there is additionally no fallback to the current checkout, the epic folder or the start folder. The rule is enforced in one shared place in the workflow runtime (not re-implemented per workflow), so a new workflow inherits it.
- REPO-WIDE SHELL-DISPATCH LINT (duplication audit C2; covers EVERY workflow, not only workspace dispatches): a test fails when any agent dispatch in any templates/workflows-js/*.js whose prompt instructs the agent to run a shell command names an agentType whose config/agent_registry.json entry does not have permits_shell: true (absent counts as not permitted). The workflow set is enumerated from the directory and the registry is read at test time -- no hard-coded lists. What counts as "a prompt that runs a shell command" is one declared, reviewed rule held in one place in the test (e.g. the prompt, including template-literal fragments, names a command line starting with git, gh, python/python3, node/npm, pytest, rm, mv, cp, bash/sh or pwsh), and the test carries a self-check proving the rule catches a known status-checker git dispatch. Each failure names the workflow, the dispatch label or location, the agentType and the command seen.
- Blast radius of the lint (verified 2026-09-25): 62 dispatches target status-checker (permits_shell: false), and only worktree-agent has permits_shell: true -- commit, test-runner, python-coder and others have no permits_shell field at all. The lint therefore goes red on today's tree. Making it green is in scope of this record: each offending dispatch is moved to a shell-permitted agent, or the registry entry of an agent that genuinely runs shell by charter gains permits_shell: true with that charter change reviewed; no dispatch is exempted by name.
- Commit spelling (KI-CG-20260925-commit-delegation-hook-misses-git-dash-c): no workflow prompt this record touches spells a commit as `git -C <path> commit`; commits go through the commit agent per CLAUDE.md Commit Delegation.
- The set of workflows under test is every workflow in the deployed workflow set, and the set of shell-permitted agents is read from config/agent_registry.json (permits_shell: true) at test time -- neither is a hard-coded list, so a new workflow or a changed registry entry inherits the check.

## Agent Contracts

### python-coder

- [ ] AC-1: BO-4300c-3-i -- Success reported with output that is not a valid answer is a failure, never 'use the current checkout'
- [ ] AC-2: BO-4300c-3-ii -- An agent that declines the workspace step ends the run, and no other command is substituted
- [ ] AC-3: BO-4300c-3 -- Every caller stops on anything but a ready answer
- [ ] AC-4: BO-4300a-1-ia -- No workflow body asks an agent to make a workspace in its own words

**Depends on:** test-writer's red baseline for the tests above and the producers under Expects From.

### llm-expert

- [ ] AC-4: BO-4300a-1-ia -- No workflow body asks an agent to make a workspace in its own words

**Depends on:** test-writer's red baseline for the tests above and the producers under Expects From.

### test-writer

- [ ] AC-1: red tests for BO-4300c-3-i per `## Test Requirements`
- [ ] AC-2: red tests for BO-4300c-3-ii per `## Test Requirements`
- [ ] AC-3: red tests for BO-4300c-3 per `## Test Requirements`
- [ ] AC-4: red tests for BO-4300a-1-ia per `## Test Requirements`

**Delivers to:** python-coder, llm-expert (red baseline).

### documentation-expert

- [ ] AC-4: reference | docs/agents/utility/shell-runner.md | agent card for the new shell-runner agent
- [ ] AC-4: reference | docs/agents/README.md | row for shell-runner in the agent table
- [ ] AC-4: explanation | docs/architecture/components/agent-registry.md | permits_shell and the one shell executor

**Depends on:** adr-author (the shell-runner ADR).

### Expects From

- **BO-4300c-3-i <- BO-4300c-3** (this ticket): The workflow acceptance predicate.
- **BO-4300c-3-ii <- BO-4300c-3** (this ticket): The workflow acceptance predicate.
- **BO-4300c-3 <- BO-4300c-2** (03_TICKET-20260928-BO-4300-answer-contract.md): The maker's JSON answer per BO-4300c-2: halt unless status == 'ok' and workspace_path is a non-empty string; take the location only from workspace_path (worktree_path is its alias).
- **BO-4300a-1-ia <- BO-4300a-1-ib** (09_TICKET-20260928-BO-4300-entry-skills.md): args.workspace: the maker's ensure answer (a JSON object per BO-4300c-2) passed verbatim by the workflow's entry command or skill; absent when the workflow must obtain the workspace itself via one verbatim dispatch.

### Delivers To

- **BO-4300c-3 -> python-coder**: WORKSPACE-ANSWER block, consumed by BO-4300a-1-ia, BO-4300c-4 and every workflow that needs a workspace. Single tracked source (e.g. templates/workflows-js/_shared/workspace-answer.js, name provisional), inlined by the workflow build phase between `// WORKSPACE-ANSWER-START` and `// WORKSPACE-ANSWER-END`. It exposes two functions: an acceptance predicate taking the raw answer (object or string) and returning either {accepted: true, answer: object, workspace_path: string} or {accepted: false, reason: string, received: string (bounded to 2 KB)}; and a dispatch helper taking the exact absolute maker command and returning the raw reply of exactly one agent() dispatch to a permits_shell agent, carrying the BO-4300c-2 schema and the instruction to run the command unchanged and relay stdout verbatim. Neither function falls back to any location when the answer is not accepted.
- consumed by **BO-4300c-5** in 13_TICKET-20260928-BO-4300-docs-and-diagrams.md
- consumed by **BO-4300f-1** in 11_TICKET-20260928-BO-4300-workflow-routes.md

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |

## Risk & Safety

- Touches money? No.
- Touches data? No production data; developer repositories are protected by the ticket 02 session guard.
- Reversibility: all changes are code/docs on the epic branch; nothing ships until the epic PR merges.

## Sign-offs

- [ ] architect-review
- [ ] adr-author
- [ ] test-writer
- [ ] python-coder
- [ ] llm-expert
- [ ] test-runner
- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] ac-validator
- [ ] ac-fulfillment-gate
- [ ] documentation-verifier
- [ ] commit

## Comments

_(Append-only log -- leave blank when authoring.)_
