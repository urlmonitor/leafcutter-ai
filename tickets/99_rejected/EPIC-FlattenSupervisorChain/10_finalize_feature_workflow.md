---
title: "Convert finalize-feature to a JS workflow script"
status: todo
components:
  - build_pipeline
created: 2026-06-02
depends_on: []
priority: high
phase: "Phase 1"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/workflows-js/finalize-feature.js
  - templates/workflows/finalize-feature.md
agents:
  architect-review: needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
user_facing_surface: slash_command
actuation_contract: "Runs all 6 finalization steps (open PR, merge, sync, test, close tickets, remove worktree) in order, with prompt() gates on destructive steps, and returns status: ok with a per-step summary on success."
---

# 10: Convert finalize-feature to a JS workflow script

## Actor / Goal

In order to make the feature-finalization pipeline deterministic and resumable
at the JS layer (matching the pattern set by `build-ticket.js` and
`build-epic.js`), we need to convert `finalize-feature` from an agent-based
MD wrapper into a `finalize-feature.js` workflow script, so that the entire
6-step finalization sequence is driven by explicit JS control flow rather than
LLM prose, and can be called as a sub-workflow by `debug.js` or `build-epic.js`.

## Context

Currently `templates/workflows/finalize-feature.md` is a thin wrapper that
invokes the `finalize-feature` agent. The agent is defined in
`templates/agents/finalize-feature.md` and orchestrates 6 sequential steps:
open PR if missing, merge PR, sync main, run tests, close tickets, remove
worktree.

This agent-based design violates the depth-1 limit when called from
`build-epic.js` (which calls `workflow("finalize-feature", ...)`) because the
workflow would then spawn the agent at depth 1, which would attempt to dispatch
further agents at depth 2. The JS script eliminates that nesting by making
every specialist dispatch a flat `agent()` call from inside the script.

Additionally, the current agent-only path is not resumable: if it crashes after
step 3 (sync main) and before step 5 (close tickets), re-running
`/finalize-feature` has no mechanism to detect that step 3 already completed.
The JS script implements resumability via state probes before each step.

This ticket is the final workflow conversion in the EPIC-FlattenSupervisorChain
sequence. Tickets 01–09 completed the core supervisor chain; this ticket adds
the finalization workflow.

### Design constraints

- `finalize-feature.js` MUST NOT call `workflow()` internally. It is a leaf
  workflow callable by `debug.js` or `build-epic.js` via
  `workflow("finalize-feature", {...})`. Calling `workflow()` from inside a
  workflow that is itself a sub-workflow would reintroduce nesting.
- Uses only `agent()` and `parallel()` internally for specialist dispatch.
- Uses `prompt()` for confirmation gates on destructive steps (merge, remove
  worktree). Steps 1, 3, and 4 are non-destructive and need no gate.
- Resumable: each step probes observable state before running, so re-running
  after a crash skips already-completed steps automatically.

### Step map

| Step | Action | Agent | Gate |
|------|--------|-------|------|
| 1 | Open PR if missing | `pull-request` | None (non-destructive) |
| 2 | Merge PR to main | `pull-request` (merge path) | `prompt()` — destructive |
| 3 | Sync local main | shell via `status-checker` | None |
| 4 | Run tests on main | `test-runner` | None — but HALT on failure |
| 5 | Close tickets / archive epic | `status-checker` | None (state-driven) |
| 6 | Remove worktree | `worktree-agent` | Gate is inside `worktree-agent`; do not double-gate |

### Resumability probes

Each step checks whether it has already completed before dispatching:

- **Step 1**: `gh pr list --head <branch>` — if a PR is open, skip dispatch,
  record the PR number, and proceed.
- **Step 2**: `gh pr view <number> --json state` — if `state == "MERGED"`,
  skip the merge prompt and proceed to step 3.
- **Step 3**: `git branch --show-current` — if already on `main`, probe
  `git status --porcelain` to verify a clean main; skip if up-to-date.
- **Step 4**: Always runs (tests on current state of main cannot be skipped).
- **Step 5**: Probe ticket file frontmatter via `status-checker`; if all
  relevant tickets are already `status: done`, skip.
- **Step 6**: `git worktree list --porcelain` — if the feature branch worktree
  is absent, skip.

### Test failure halt (step 4)

On test failure, the workflow returns immediately with:

```json
{
  "status": "halted",
  "halted_at_step": 4,
  "reason": "post_merge_test_failure",
  "message": "Post-merge tests failed on main. Tickets have NOT been closed. Worktree has NOT been removed.",
  "test_output": "<test-runner failure output verbatim>",
  "action_required": "Fix the regression on a new branch, then re-run /finalize-feature."
}
```

Steps 5 and 6 are NOT executed.

### Relationship to finalize-feature.md (agent template)

`templates/agents/finalize-feature.md` remains as the fallback for Claude Code
versions older than 2.1.154 (same dual-path build gate used for other workflow
scripts). `templates/workflows/finalize-feature.md` is updated to document the
dual path and reference `finalize-feature.js`, matching the pattern in
`templates/workflows/create-ticket.md`.

### Architectural context

This script runs in the same runtime environment as `build-ticket.js` and
`build-epic.js`. The Claude Code workflow runtime provides `agent()`,
`parallel()`, `prompt()`, and `workflow()` as injected functions. The `run()`
function signature must accept `{ userInput, agent, parallel, prompt }`.

The `workflow()` function is intentionally absent from the parameter destructure
to signal the leaf-workflow constraint (and to prevent accidental recursive
workflow calls during implementation).

## Acceptance Criteria

```gherkin
Given finalize-feature.js exists in templates/workflows-js/
When the file is reviewed
Then it contains a meta object with name "finalize-feature"
 And it contains a run() function accepting { userInput, agent, parallel, prompt }
 And it does NOT call workflow() anywhere in the file

Given /finalize-feature is invoked on a feature branch with no open PR
When step 1 executes
Then the pull-request agent is dispatched to open the PR
 And the resulting PR number is recorded and used in subsequent steps

Given /finalize-feature is invoked and a PR is already open
When step 1 executes
Then the workflow logs "PR already open (#N) — skipping step 1"
 And the pull-request agent is NOT dispatched for step 1

Given /finalize-feature reaches step 2 (merge)
When the user is prompted and answers "no"
Then the workflow returns status: "halted" with message "Finalization halted at merge step"
 And no further steps execute

Given /finalize-feature reaches step 2 and the PR is already merged
When step 2 executes
Then the merge prompt is skipped
 And the workflow proceeds directly to step 3

Given step 4 (test-runner) reports test failures
When the workflow processes the test-runner result
Then it returns status: "halted" with halted_at_step: 4
 And steps 5 and 6 are NOT executed
 And the test output is included in the returned error

Given all 6 steps complete successfully
When the workflow returns
Then status is "ok"
 And the result includes a per-step summary listing completed and skipped steps

Given templates/workflows/finalize-feature.md is reviewed
When the file is read
Then it contains a reference to finalize-feature.js as the primary dispatch path
 And a fallback comment for pre-2.1.154 Claude Code versions
```

## Implementation Tasks

- [ ] Create `templates/workflows-js/finalize-feature.js` with:
  - Top-level JSDoc header (same format as `build-ticket.js` and `build-epic.js`)
  - `const meta` object: `name: "finalize-feature"`, `description`, `phases` array
  - `async function run({ userInput, agent, parallel, prompt })` — note: no
    `workflow` in destructure (leaf workflow constraint)
  - Pre-flight: extract `BRANCH` and `WORKTREE_ROOT` via `status-checker` agent;
    halt with structured error if branch is `main` or `master`
  - Step 1: probe `gh pr list --head BRANCH`; dispatch `pull-request` agent if
    no PR found; record PR number from either path
  - Step 2: probe `gh pr view <number> --json state`; if not merged, call
    `prompt()` to confirm merge; dispatch `pull-request` agent (merge path);
    halt with `status: "halted"` on user refusal
  - Step 3: dispatch `status-checker` agent to run `git checkout main && git pull`;
    record new HEAD SHA
  - Step 4: dispatch `test-runner` agent; on failure return
    `{ status: "halted", halted_at_step: 4, reason: "post_merge_test_failure", ... }`;
    do NOT proceed to step 5 or 6 on failure
  - Step 5: dispatch `status-checker` agent to detect branch scope (single
    ticket vs epic) and move ticket files to `done/`; handle both single-ticket
    and epic-archive paths
  - Step 6: dispatch `worktree-agent remove <WORKTREE_ROOT>`; surface any
    `conflict_pids` verbatim and stop if present
  - Return `{ status: "ok", branch, pr_number, completed_steps, skipped_steps, message }`
    on full success
- [ ] Update `templates/workflows/finalize-feature.md`:
  - Replace the current body with the dual-path pattern:
    ```
    Invoke `finalize-feature.js` (Claude Code >= 2.1.154) or the
    `finalize-feature` agent (older versions) with: $ARGUMENTS
    ```
  - Keep the existing `description:` frontmatter; update it to reference the JS
    workflow as the primary path

## Risk & Safety

- Touches money? No.
- Touches data? No — ticket file moves are reversible via `git mv` revert.
- Reversibility? The `.js` file is additive. The `.md` update is a two-line
  change and is trivially reverted. The dual-path build gate ensures older
  installs continue using the agent path unchanged.
- Destructive steps (merge, worktree removal) are always gated behind
  `prompt()` or delegated to agents that own their own gates. The script
  itself never runs `git merge`, `git push --force`, or `rm -rf` directly.
- Test failure hard-halt before step 5 prevents ticket files from being
  moved to `done/` after a broken merge — this is the key safety invariant.

## Smoke Fixture

```yaml
surface: finalize-feature
fixture_input: |
  (no arguments — workflow reads branch and worktree from git context)
assertion: "status.*ok|PR already open|Finalization halted"
placeholder_signature: "Invoke the .finalize-feature. agent"
```

## Comments

_(Append-only log — leave blank when authoring.)_
