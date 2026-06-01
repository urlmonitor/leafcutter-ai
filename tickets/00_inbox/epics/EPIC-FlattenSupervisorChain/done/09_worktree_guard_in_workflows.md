---
title: "Add worktree guard and auto-creation to build-epic.js and build-ticket.js"
status: done
components:
  - build_pipeline
created: 2026-06-01
depends_on: []
priority: high
phase: "Phase 1"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/create-ticket.js
  - unit_tests/test_build_epic_workflow.py
  - unit_tests/test_build_ticket_workflow.py
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
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
user_facing_surface: null
---

# 09: Add worktree guard and auto-creation to build-epic.js and build-ticket.js

## Actor / Goal

In order to prevent implementation work from running on the main branch and
corrupting the shared working tree, we need `build-epic.js` and
`build-ticket.js` to check whether they are running inside a git worktree
and, if not, automatically create one before proceeding — so that the
project's worktree convention is enforced without requiring the caller to
have done so manually.

## Context

A post-implementation audit of the three JS workflow scripts created as part
of EPIC-FlattenSupervisorChain (`build-epic.js`, `build-ticket.js`,
`create-ticket.js`) revealed that `build-epic.js` and `build-ticket.js`
contain zero worktree logic. The happy path works because `build-feature.md`
(Step A) creates a worktree before dispatching. However, if either workflow is
invoked directly — e.g. `Workflow({name: 'build-epic', ...})` — all
implementation work runs on `main`, which is the catastrophic scenario the
project's worktree convention was designed to prevent.

Additionally, `build-epic.js` does not pass `worktree_path` to its
`workflow("build-ticket", ...)` sub-calls, so even when a worktree exists,
child tickets lose the context.

`create-ticket.js` is a planning tool that intentionally runs on main (ticket
creation does not modify code). It does NOT need a worktree guard. It needs
only a documentation comment clarifying this design intent.

### How to detect "already in a worktree"

A git worktree's `.git` entry is a **file** (not a directory) containing a
`gitdir:` pointer back to the main repo. In the main clone, `.git` is a
directory. Two complementary checks are therefore reliable without shelling out:

1. **Branch check**: if the current branch is `main` or `master`, we are likely
   on the main clone. (Worktrees always check out a non-main branch.)
2. **`.git` file check**: run `stat .git` — if `.git` is a regular file (not a
   directory), we are inside a worktree.

Either check alone can false-positive; using both together is robust. Prefer
the `.git`-is-a-file check as primary (most reliable), with the branch-name
check as a secondary signal.

### Worktree creation approach

The CLAUDE.md note confirms `scripts/setup_ticket_worktree.py` does not exist
yet at deploy time; the built-in `EnterWorktree` tool is the recommended
alternative. However, `EnterWorktree` is a Claude Code tool, not a bash
command — it cannot be invoked from within a workflow JS script directly.

The correct approach for the JS layer is to emit a **structured error** with
a clear `action_required` field that instructs the caller to run worktree
setup before re-invoking. This is preferable to silently creating a worktree,
because:

- Workflow scripts run with limited context (no git credentials, no push
  access assumptions).
- Creating a worktree requires knowing the target branch name, which the
  workflow script may not have.
- A clear structured error prevents silent main-branch contamination while
  giving the caller (human or `/build-feature`) everything needed to recover.

The guard must:
1. Detect whether `.git` is a file (worktree) or directory (main clone).
2. On main clone: return a structured `error` result with a `worktree_required`
   key and an instructional message. Do NOT proceed.
3. On worktree: continue normally.
4. In `build-epic.js`, also propagate the `worktree_path` (resolved from the
   CWD) to all `workflow("build-ticket", ...)` calls so child tickets have
   the path in their input.

### Why a "run the script" approach is not viable here

The audit note mentions "just bash calls to existing scripts" for worktree
creation. `templates/scripts/setup_ticket_worktree.py` exists in the template
tree but CLAUDE.md explicitly warns it does not exist yet in the deployed
project. Running a missing script would produce a worse failure than the
structured error. The structured-error guard is the correct first
implementation.

A follow-up ticket can add actual auto-creation once
`setup_ticket_worktree.py` is reliably deployed (tracked separately).

### `build-epic.js` sub-workflow propagation gap

In `build-epic.js` Step 4, each parallel slot calls:

```js
await workflow("build-ticket", { ticket_path: ticket.path })
```

The `worktree_path` is not passed, so if `build-ticket.js` ever needs to
resolve relative paths or communicate worktree context to phase agents, it
has no way to do so. This ticket also adds `worktree_path` to the input
object here.

## Acceptance Criteria

```gherkin
Given build-epic.js is invoked and CWD has .git as a directory (main clone)
When the workflow script runs
Then it returns status: "error" with worktree_required: true
 And the message describes how to create a worktree before re-running
 And no planner agent is dispatched

Given build-epic.js is invoked and CWD has .git as a file (worktree)
When the workflow script runs
Then the worktree guard passes
 And execution proceeds to the planner agent normally

Given build-ticket.js is invoked and CWD has .git as a directory (main clone)
When the workflow script runs
Then it returns status: "error" with worktree_required: true
 And no planner agent is dispatched

Given build-ticket.js is invoked and CWD has .git as a file (worktree)
When the workflow script runs
Then the worktree guard passes and the planner agent is dispatched

Given build-epic.js dispatches build-ticket sub-workflows within a batch
When a ticket slot is dispatched via parallel()
Then the input object passed to workflow("build-ticket", ...) includes worktree_path

Given create-ticket.js
When reviewed by a developer
Then a comment near the top of the file explicitly states the script is
 intentionally designed to run on main and requires NO worktree
```

## Implementation Tasks

- [ ] In `build-epic.js` `run()`: add a worktree detection helper function
  `isInWorktree()` that shells out via the `agent` mechanism or uses JS
  `fs`/`path` to check whether `.git` is a regular file. Return a structured
  `{ status: "error", worktree_required: true, message: "..." }` immediately
  if not in a worktree.
- [ ] In `build-ticket.js` `run()`: add the same `isInWorktree()` guard at
  the top of the function, before the planner agent call.
- [ ] In `build-epic.js` Step 4 (parallel dispatch), add `worktree_path`
  (resolved from `process.cwd()` or passed in via `params`) to each
  `workflow("build-ticket", { ticket_path: ticket.path, worktree_path })` call.
- [ ] In `create-ticket.js`: add a JSDoc comment block at the top of `run()`
  explaining that this workflow intentionally runs on main (planning tool,
  does not modify code files) and should NOT have a worktree guard.
- [ ] Add unit tests in `unit_tests/test_build_epic_workflow.py` covering the
  new worktree guard: main-clone detection returns structured error; worktree
  detection allows continuation; worktree_path propagation to sub-calls.
- [ ] Add unit tests in `unit_tests/test_build_ticket_workflow.py` covering
  the new worktree guard: main-clone detection returns structured error;
  worktree detection allows continuation.
- [ ] Run `pytest unit_tests/test_build_epic_workflow.py unit_tests/test_build_ticket_workflow.py`
  and confirm all tests pass.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? The guard is additive. If it incorrectly fires (false
  positive in an unusual git layout), the only consequence is a structured
  error instead of proceeding. The user can re-run after verifying their git
  layout. No data is modified; no agents are spawned before the check passes.
- The check reads filesystem state (`.git` file vs directory) and does not
  make network calls.
- No changes to the agent registry, build.py, or any deployed hook.

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
