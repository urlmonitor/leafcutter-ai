---
title: "Convert debug skill to composed JS workflow script (debug.js)"
status: todo
components:
  - build_pipeline
created: 2026-06-02
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
user_facing_surface: slash_command
actuation_contract: "Dispatches three parallel investigative agents, synthesizes findings, creates a fix ticket via create-ticket workflow, builds it via build-ticket workflow, and optionally runs finalize-feature — printing a structured result with status, investigation_summary, ticket_path, build_result, and finalize_result."
files_touched:
  - templates/workflows-js/debug.js
  - templates/workflows/debug.md
  - templates/skills/debug/SKILL.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  user-surface-smoker: needed
ac_traceability:
  L0: BP-300
  L1: BP-300a
  ac_path: docs/acceptance-criteria/build_pipeline/BP-300-workflow-orchestration/BP-300a.yaml
  routing: direct_to_ba
---

# Convert debug skill to composed JS workflow script (debug.js)

## Actor / Goal

In order to bring the `/debug` command into the deterministic JS workflow
architecture (ADR-006), we need to convert the prose-based `debug` skill into
a `debug.js` workflow script that composes existing leaf workflows, so that
agent dispatch is flat, depth-bounded, and crash-resumable.

## Context

Currently `/debug` is implemented as a prose skill at
`templates/skills/debug/SKILL.md`. The main loop reads the skill and spawns
Agent tool calls inline, which means orchestration logic lives in the LLM's
working context rather than a deterministic script. This is the same anti-pattern
that ADR-006 eliminated for `build-ticket`, `build-epic`, and `create-ticket`.

The fix follows the exact same conversion pattern:

- **Pattern file**: `templates/workflows-js/build-epic.js` — meta object with
  `phases` array, `async function run({ userInput, agent, workflow, parallel, prompt })`,
  structured return object.
- **Pattern file**: `templates/workflows-js/create-ticket.js` — demonstrates use
  of `prompt()` for user clarification mid-workflow and `workflow()` for calling
  child workflows.
- **Pattern file**: `templates/workflows-js/build-ticket.js` — demonstrates
  `agent()` dispatch and sequential phase loops.

The debug workflow is a **ROOT workflow only** — it calls `workflow()` internally
to invoke `create-ticket`, `build-ticket`, and `finalize-feature`. It can NEVER
be dispatched as a child workflow by another workflow.

The three investigative agents in Phase 1 use `agentType: "Explore"` (read-only
search agents) dispatched concurrently via `parallel()`. After they return, a
single synthesis `agent()` call merges their reports. If the synthesis reveals
conflicts or low confidence, `prompt()` asks the user for clarification before
the ticket is created.

Phase 3 calls `workflow("build-ticket", ...)` directly — NOT `build-epic` —
because `/debug` always produces a single focused fix ticket, never an epic.

Phase 4 (finalize) is optional: the workflow calls `prompt()` to ask the user
whether to finalize or leave for manual review.

The existing `templates/workflows/debug.md` (the prose command entrypoint) must
be updated to reference `debug.js` as the primary implementation and include a
fallback comment for Claude Code installs older than 2.1.154.

The existing `templates/skills/debug/SKILL.md` must receive a note at the top
that it is superseded by `debug.js` for Claude Code >= 2.1.154, and that the
skill remains as a fallback only.

## Acceptance Criteria

```gherkin
Given debug.js exists at templates/workflows-js/debug.js
When a Claude Code runtime >= 2.1.154 loads /debug
Then it executes debug.js (not the prose skill) and dispatches three
  parallel Explore agents in Phase 1

Given the three investigative agents all return high-confidence, agreeing reports
When the synthesis agent merges their output
Then the workflow proceeds directly to create-ticket without calling prompt()

Given the three investigative agents return conflicting or low-confidence reports
When the synthesis agent merges their output and flags uncertainty
Then the workflow calls prompt() with targeted questions before creating a ticket

Given the create-ticket workflow succeeds and returns a ticket_path
When Phase 3 (build-ticket) is reached
Then the workflow calls workflow("build-ticket", { userInput: ticket_path })
  and NOT workflow("build-epic", ...)

Given build-ticket succeeds
When Phase 4 (finalize) is reached
Then the workflow calls prompt() asking the user whether to finalize or skip,
  and respects the user's answer before proceeding or returning

Given the workflow completes (with or without finalize)
When it returns
Then the return object contains status, investigation_summary, ticket_path,
  build_result, and finalize_result (null when skipped)

Given templates/workflows/debug.md is updated
When a Claude Code runtime < 2.1.154 loads /debug
Then debug.md falls back to the prose skill at .claude/skills/debug/SKILL.md

Given templates/skills/debug/SKILL.md is updated
When an agent reads the skill file
Then the first section contains a note that this skill is superseded by debug.js
  for Claude Code >= 2.1.154 and acts as a fallback only
```

## Sign-offs

- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request
- [ ] user-surface-smoker

## Comments

## Smoke Fixture

```yaml
surface: debug
fixture_input: |
  TypeError in the login endpoint when email is None
assertion: "investigation_summary|ticket_path|status"
placeholder_signature: "SKILL.md|read and follow|prose skill"
```

## Implementation Tasks

### documentation-expert

- [ ] Create `templates/workflows-js/debug.js` with the following structure:
  - Top-of-file JSDoc block referencing the ticket, the prose skill it replaces,
    minimum Claude Code version (2.1.154), and fallback path.
  - `const meta` object: `name: "debug"`, `description` summarising the
    four-phase pipeline, `phases` array matching the four phases below.
  - `async function run({ userInput, agent, workflow, parallel, prompt })`:

    **Phase 1 — Investigate** (`parallel()`):
    - Guard: if `userInput` is empty, return a structured error asking the
      user to describe the issue.
    - Dispatch three agents concurrently via `parallel([...])`:
      - `agent({ agentType: "Explore", input: { role: "database", issue: userInput, instructions: "<database investigation mandate from SKILL.md §Agent 1>" } })`
      - `agent({ agentType: "Explore", input: { role: "backend",  issue: userInput, instructions: "<backend investigation mandate from SKILL.md §Agent 2>" } })`
      - `agent({ agentType: "Explore", input: { role: "frontend_docs", issue: userInput, instructions: "<frontend/docs investigation mandate from SKILL.md §Agent 3>" } })`
    - After all three return, call a synthesis `agent()`:
      `agent({ agentType: "brainstorm-lead", input: { reports: [db_report, backend_report, frontend_report], issue: userInput, instructions: "Synthesize the three investigative reports. Return JSON: { agreed_findings, conflicting_findings, uncertain_areas, docs_discrepancies, root_cause, fix_plan, confidence: high|medium|low, needs_user_clarification: bool, clarification_questions: [] }" } })`

    **Clarification gate** (between Phase 1 and Phase 2):
    - Parse synthesis JSON; if `needs_user_clarification` is `true`, call:
      `await prompt("Investigation complete. The following points need clarification before a ticket is created:\n\n" + clarification_questions.join("\n") + "\n\nYour answers:")`
    - Store user answers in `userClarifications`.

    **Phase 2 — Create ticket** (`workflow()`):
    - Build a detailed input string: original issue + root cause + fix plan +
      docs discrepancies + files to touch + user clarifications (if any).
    - `const createResult = await workflow("create-ticket", { userInput: ticketInput })`
    - Extract `ticket_path = createResult.ticket_path`.
    - If `ticket_path` is falsy, return `{ status: "error", message: "create-ticket did not return a ticket_path", ... }`.

    **Phase 3 — Build ticket** (`workflow()`):
    - `const buildResult = await workflow("build-ticket", { userInput: ticket_path })`

    **Phase 4 — Finalize (optional)** (`prompt()` + `workflow()`):
    - `const answer = await prompt("Build complete. Run /finalize-feature now to open a PR and close the worktree? (yes / no)")`
    - If `answer` matches `/^y/i`, call `await workflow("finalize-feature", { userInput: ticket_path })` and store result.
    - Otherwise store `null`.

    **Return**:
    ```js
    return {
      status: "ok",
      investigation_summary: synthResult,
      ticket_path,
      build_result: buildResult,
      finalize_result: finalizeResult,
    };
    ```

  - Wrap all `workflow()` calls in try/catch returning `{ status: "error", ... }`
    on failure (consistent with build-epic.js error handling pattern).

- [ ] Update `templates/workflows/debug.md`:
  - Prepend a block at the top of the body (after frontmatter) explaining that
    for Claude Code >= 2.1.154 this command is executed by `debug.js`; the prose
    below is the fallback for older installs.
  - Leave all existing prose content intact (so older runtimes still work).

- [ ] Update `templates/skills/debug/SKILL.md`:
  - Insert a `## Superseded by debug.js` note as the first section after the
    frontmatter header, stating: "For Claude Code >= 2.1.154 this skill is
    superseded by `templates/workflows-js/debug.js`. The prose below acts as a
    fallback for older installs and as developer documentation for the workflow's
    intent. Do not remove this file."
  - Leave all existing skill content intact beneath the note.

- [ ] Verify `debug.js` is syntactically valid JavaScript (no parse errors) by
  running: `node --check templates/workflows-js/debug.js` and confirming exit 0.

## Risk & Safety

- Touches money? No.
- Touches data? No — workflow script and documentation files only.
- Reversibility? Fully reversible. All three modified files are version-controlled
  text. `git revert` restores the previous state. The prose skill remains in place
  as a fallback; no capability is removed.
- Shared contract? `templates/workflows-js/debug.js` is compiled by `build.py`
  into consumer projects. A JS parse error in `debug.js` would break the `/debug`
  command in all downstream projects on next build. The `node --check` validation
  step in Implementation Tasks guards against this.
- ROOT-only constraint: `debug.js` must never be listed as a child workflow in any
  other workflow. The `meta` object should document this constraint explicitly.
  Violation would create unbounded recursion (debug → create-ticket → debug ...).
