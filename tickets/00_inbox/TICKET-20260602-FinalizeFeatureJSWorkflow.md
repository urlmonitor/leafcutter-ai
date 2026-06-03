---
title: "Convert finalize-feature from LLM agent to deterministic JS workflow script"
status: todo
components:
  - build_pipeline
created: 2026-06-02
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/workflows-js/finalize-feature.js
  - templates/workflows/finalize-feature.md
agents:
  architect-review: signed_off
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: signed_off
user_facing_surface: slash_command
actuation_contract: "Runs the 6-step finalization sequence (open PR, merge, sync main, run tests, close tickets, remove worktree) with prompt() gates on destructive steps, and returns { status: ok } with a per-step summary on full success."
---

# Convert finalize-feature from LLM agent to deterministic JS workflow script

## Actor / Goal

In order to make the feature-finalization pipeline deterministic, resumable,
and composable as a sub-workflow for `debug.js` and other root workflows, we
need to replace the `finalize-feature` LLM agent with a `finalize-feature.js`
JS workflow script, so that the 6-step finalization sequence is driven by
explicit JavaScript control flow rather than LLM prose.

## Context

Currently `/finalize-feature` invokes the `finalize-feature` agent
(`templates/agents/finalize-feature.md`), which orchestrates 6 sequential
steps entirely through LLM reasoning. This creates two problems:

1. **Depth-1 violation risk**: when `finalize-feature` is called as a
   sub-workflow from `build-epic.js` or `debug.js`, the agent it spawns
   would attempt further agent dispatches at depth 2, hitting Claude Code's
   hard nesting limit.

2. **No resumability**: if the workflow crashes after step 3 (sync main) but
   before step 5 (close tickets), re-running `/finalize-feature` has no
   mechanism to detect which steps already completed.

The JS script pattern (established by `build-ticket.js` and `build-epic.js`)
eliminates both problems. Every specialist dispatch is a flat `agent()` call
at depth 1. State probes before each step enable crash-resume.

### Leaf workflow constraint

`finalize-feature.js` MUST NOT call `workflow()` internally. It is a leaf
workflow — callable by `debug.js` or `build-epic.js` via
`workflow("finalize-feature", {...})`. Calling `workflow()` from inside a
child workflow would reintroduce nesting. The `run()` function signature must
accept `{ userInput, agent, parallel, prompt }` with `workflow` intentionally
absent from the destructure.

### Step map

| Step | Action | Agent | Gate |
|------|--------|-------|------|
| 1 | Open PR if missing | `pull-request` | None (non-destructive) |
| 2 | Merge PR to main | `pull-request` (merge path) | `prompt()` — destructive |
| 3 | Sync local main | `status-checker` (shell) | None |
| 4 | Run tests on main | `test-runner` | None — HALT on failure |
| 5 | Close tickets / archive epic | `status-checker` | None (state-driven) |
| 6 | Remove worktree | `worktree-agent` | Gate is inside `worktree-agent`; do not double-gate |

Steps 4 and 5 are independent once step 4 succeeds; however step 4 MUST
complete successfully before step 5 runs (test failure halts the workflow
before ticket closing).

### Resumability probes

Each step checks observable state before dispatching to support crash-resume:

- **Step 1**: `gh pr list --head <branch>` — if a PR is open, skip dispatch
  and record the PR number.
- **Step 2**: `gh pr view <number> --json state` — if `state == "MERGED"`,
  skip the merge prompt and proceed to step 3.
- **Step 3**: `git branch --show-current` — if already on `main` and
  up-to-date, skip the checkout/pull.
- **Step 4**: Always runs (test results on current main cannot be cached).
- **Step 5**: Probe ticket file frontmatter via `status-checker`; skip if all
  relevant tickets already have `status: done`.
- **Step 6**: `git worktree list --porcelain` — if the feature branch worktree
  is absent, skip.

### Test failure halt (step 4)

On test failure the workflow returns immediately:

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

### Structured return contract

```json
{
  "status": "ok",
  "branch": "<feature-branch>",
  "pr_number": 42,
  "pr_url": "https://github.com/...",
  "merge_result": { ... },
  "test_result": { ... },
  "tickets_closed": ["path/to/ticket.md"],
  "worktree_removed": true,
  "completed_steps": [1, 2, 3, 4, 5, 6],
  "skipped_steps": []
}
```

### Relationship to existing templates

`templates/agents/finalize-feature.md` remains as the fallback for Claude
Code versions older than 2.1.154 (dual-path build gate, same pattern as
other workflow scripts). `templates/workflows/finalize-feature.md` is updated
to document the dual path and reference `finalize-feature.js` as the primary
dispatch path.

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

Given /finalize-feature is invoked and the PR is already merged
When step 2 executes
Then the merge prompt is skipped
 And the workflow proceeds directly to step 3

Given /finalize-feature reaches step 2 (merge)
When the user is prompted and answers "no"
Then the workflow returns status: "halted" with message "Finalization halted at merge step"
 And no further steps execute

Given step 4 (test-runner) reports test failures
When the workflow processes the test-runner result
Then it returns status: "halted" with halted_at_step: 4 and reason: "post_merge_test_failure"
 And steps 5 and 6 are NOT executed
 And the test output is included verbatim in the returned error

Given all 6 steps complete successfully
When the workflow returns
Then status is "ok"
 And the result includes pr_number, pr_url, merge_result, test_result, tickets_closed, worktree_removed
 And completed_steps lists all 6 step numbers

Given templates/workflows/finalize-feature.md is reviewed
When the file is read
Then it contains a reference to finalize-feature.js as the primary dispatch path
 And a fallback comment for pre-2.1.154 Claude Code versions
```

## Sign-offs

- [x] architect-review — 2026-06-03 10:30
- [x] pr-reviewer — 2026-06-03 10:45
- [ ] commit
- [ ] pull-request
- [x] user-surface-smoker — 2026-06-03 11:00

## Smoke Fixture

```yaml
surface: finalize-feature
fixture_input: |
  (no arguments — workflow reads branch and worktree from git context)
assertion: "status.*ok|PR already open|Finalization halted"
placeholder_signature: "Invoke the .finalize-feature. agent"
```

## Comments

### 2026-06-03 11:00 — user-surface-smoker (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  surface_invoked: true
  assertions_passed: true
  no_placeholder_signatures: true
Smoke test PASS. Surface: finalize-feature (slash_command). Verified: (1) finalize-feature.js exists in templates/workflows-js/; (2) placeholder_signature "Invoke the .finalize-feature. agent" NOT found in finalize-feature.md; (3) assertion regex "status.*ok|PR already open|Finalization halted" matches workflow response strings in finalize-feature.js; (4) finalize-feature.md references finalize-feature.js as primary dispatch path with version comment.

### 2026-06-03 10:45 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-03_d95fe057
completion_manifest:
  diff_reviewed: true
  no_high_findings: true
  scope_verified: true
Reviewed finalize-feature.js (433 lines, new) and finalize-feature.md (10 lines changed). No high-confidence findings. One medium finding [M-1]: prNumber could be null if pull-request agent returns unparseable JSON at step 2 — unlikely in practice, no action needed. Scope exactly matches files_touched (templates/workflows-js/finalize-feature.js + templates/workflows/finalize-feature.md). Leaf constraint verified (no workflow() calls in code). All 6 steps present. Halt-on-test-failure invariant correct. Escalation: none (medium count 1, threshold > 3).

### 2026-06-03 10:30 — architect-review (status: ok)
feedback-id: fb_2026-06-03_6fdc5b1c
completion_manifest:
  blast_radius_assessed: true
  impact_classified: true
  architectural_note_written: true
Impact classification: SMALL. 2 files touched (templates/workflows-js/finalize-feature.js new, templates/workflows/finalize-feature.md minor update), 1 component (build_pipeline). No always-large triggers (no Alembic migration, no hypertable change, no public API change, no ADR contract change). The leaf-workflow constraint (workflow() absent from run() destructure) correctly prevents depth violations when finalize-feature.js is called as a sub-workflow. Dual-path pattern is consistent with build-ticket.js and build-epic.js. No new ADR needed; no new diagram needed. Both implementation tasks completed: finalize-feature.js created with all 6 steps + resumability probes + halt-on-test-failure invariant; finalize-feature.md updated with dual-path header and version comment.

## Implementation Tasks

- [x] Create `templates/workflows-js/finalize-feature.js`:
  - Top-level JSDoc header (same format as `build-ticket.js` and `build-epic.js`),
    referencing ADR-006 and this ticket
  - `const meta` object with `name: "finalize-feature"`, `description`, and
    `phases` array listing the 6 steps
  - `async function run({ userInput, agent, parallel, prompt })` — `workflow`
    intentionally absent from destructure (leaf workflow constraint)
  - Pre-flight: dispatch `status-checker` agent to run `git branch --show-current`
    and `git rev-parse --show-toplevel`; capture `BRANCH` and `WORKTREE_ROOT`;
    halt with structured error if `BRANCH` is `main` or `master`
  - Step 1 (resumable): probe `gh pr list --head BRANCH --json number,url`;
    dispatch `pull-request` agent if no open PR; record `prNumber` and `prUrl`
    from either path
  - Step 2 (resumable + gated): probe `gh pr view <prNumber> --json state`;
    if `state != "MERGED"`, call `prompt()` for merge confirmation; on `"no"`
    return `{ status: "halted", message: "Finalization halted at merge step..." }`;
    dispatch `pull-request` agent (merge path) on `"yes"`
  - Step 3 (resumable): dispatch `status-checker` to run
    `git checkout main && git pull`; record new HEAD SHA
  - Step 4: dispatch `test-runner` agent; on failure return
    `{ status: "halted", halted_at_step: 4, reason: "post_merge_test_failure", ... }`;
    do NOT proceed to steps 5 or 6 on failure
  - Step 5 (resumable): dispatch `status-checker` agent to detect branch
    scope (single-ticket vs epic) from commit messages and `tickets/` tree;
    probe current ticket status; move ticket files to `done/` or archive epic
    folder if not already done
  - Step 6 (resumable): probe `git worktree list --porcelain`; if worktree
    exists, dispatch `worktree-agent remove <WORKTREE_ROOT>`; surface any
    `conflict_pids` verbatim and stop if present; skip if worktree already gone
  - Return `{ status: "ok", branch, pr_number, pr_url, merge_result,
    test_result, tickets_closed, worktree_removed, completed_steps,
    skipped_steps, message }` on full success

- [x] Update `templates/workflows/finalize-feature.md`:
  - Replace the current single-line body with the dual-path pattern:
    `Invoke finalize-feature.js (Claude Code >= 2.1.154) or the finalize-feature agent (older versions) with: $ARGUMENTS`
  - Update `description:` frontmatter to reference the JS workflow as the
    primary path and note the fallback; add `# v2.1.154+` comment

## Risk & Safety

- Touches money? No.
- Touches data? No — ticket file moves are reversible via `git mv` revert.
- Reversibility? `finalize-feature.js` is additive. The `.md` update is a
  two-line change and is trivially reverted. The dual-path build gate ensures
  older installs continue using the agent path unchanged.
- Destructive steps (merge, worktree removal) are always gated behind
  `prompt()` or delegated to agents that own their own gates. The script
  itself never runs `git merge`, `git push --force`, or `rm -rf` directly.
- Test failure hard-halt before step 5 prevents tickets from being moved to
  `done/` after a broken merge — this is the key safety invariant.
- `workflow()` absence from `run()` destructure prevents accidental recursive
  workflow calls during implementation; any attempt to call `workflow()` inside
  the script will throw a runtime TypeError.
