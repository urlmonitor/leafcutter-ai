---
title: "Add PROJECT_CONTEXT.md for pull-request agent with EMU guard and PR writing standards"
status: todo
components:
  - infrastructure
created: 2026-06-04
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
user_facing_surface: agent_orchestrated
actuation_contract: "When the pull-request agent runs, it reads .agents/agents/pull-request/PROJECT_CONTEXT.md at startup, switches to the urlmonitor gh auth account before running gh pr create, and applies project PR writing standards to every draft."
files_touched:
  - templates/agents/pull-request.md
  - .agents/agents/pull-request/PROJECT_CONTEXT.md
  - tests/test_pull_request_project_context.py
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
  user-surface-smoker: not_needed
ac_coverage: 0/6
---

# Add PROJECT_CONTEXT.md for pull-request agent with EMU guard and PR writing standards

## Actor / Goal

As the operator running the pull-request phase agent on the leafcutter-ai repo, I need the agent
to (a) automatically check and switch to the `urlmonitor` GitHub account before calling
`gh pr create`, and (b) apply project-specific PR title and description standards — so that
EMU-blocked `gh pr create` failures and poor-quality PR drafts are eliminated without requiring
manual pre-drive intervention.

## Context

The pull-request agent currently calls `gh pr create` with no account check. On this project,
running under an Enterprise Managed User (EMU) GitHub account causes GitHub to return:

```
Unauthorized: As an Enterprise Managed User, you cannot access this content (createPullRequest)
```

This failure mode exhausted the full adjudication ladder in feedback entry `fb_2026-06-03_80dafa72`
because the agent retried without switching accounts. The CLAUDE.md Pre-Drive Checklist already
documents the manual fix (`gh auth switch --user urlmonitor`), but it should be automated in the
agent itself.

The `PROJECT_CONTEXT.md` convention (documented at
`docs/conventions/PROJECT_CONTEXT-injection.md`) provides the correct mechanism: a per-agent
companion file at `.agents/agents/<agent-name>/PROJECT_CONTEXT.md` that the agent reads at
startup. The pull-request template currently has no Pre-Flight step to load this file.

SSH host alias for this repo: `github.com-urlmonitor`. Correct gh auth user: `urlmonitor`.
Repo path: `/home/henzeh/projects/leafcutter/leafcutter-ai/`.

## Deliverables

1. **Pre-Flight step in `templates/agents/pull-request.md`** — insert a Pre-Flight section
   before Step 0 that reads `.agents/agents/pull-request/PROJECT_CONTEXT.md` if it exists,
   follows every pointer in that file, and logs one debug line if absent.

2. **`.agents/agents/pull-request/PROJECT_CONTEXT.md`** — project-side context file covering:
   - EMU account restriction: run `gh auth status` before `gh pr create`; if the active user is
     not `urlmonitor`, run `gh auth switch --user urlmonitor` before proceeding; warn the user
     that the account was switched.
   - PR title standards: imperative mood, present tense, 70-character limit, no trailing period.
   - PR description standards: `## Summary` (up to 3 bullets), `## Test plan` (checkbox list),
     `Generated with [Claude Code](https://claude.com/claude-code)` footer.
   - Key reference: `docs/conventions/PROJECT_CONTEXT-injection.md`.

3. **`tests/test_pull_request_project_context.py`** — wiring verification test covering:
   - The pull-request template contains the Pre-Flight load instruction referencing
     `PROJECT_CONTEXT.md`.
   - The `.agents/agents/pull-request/PROJECT_CONTEXT.md` file exists at the expected path.
   - The context file contains the EMU account check instruction (keyword: `urlmonitor`).
   - The context file contains PR title standards (keyword: `70`).

## Acceptance Criteria

- [ ] AC-1: `templates/agents/pull-request.md` contains a Pre-Flight section that instructs the
  agent to read `.agents/agents/pull-request/PROJECT_CONTEXT.md` before Step 0, and logs exactly
  one debug line (`PROJECT_CONTEXT.md not found for pull-request; running template-only`) if the
  file is absent.

- [ ] AC-2: `.agents/agents/pull-request/PROJECT_CONTEXT.md` exists and contains an EMU account
  restriction section that instructs the agent to run `gh auth status`, compare the active user
  to `urlmonitor`, and run `gh auth switch --user urlmonitor` if the active account differs —
  before any `gh pr create` call.

- [ ] AC-3: `.agents/agents/pull-request/PROJECT_CONTEXT.md` contains a PR writing standards
  section specifying: title must be imperative mood, under 70 characters, no trailing period;
  body must use the `## Summary` / `## Test plan` / footer structure defined in the template.

- [ ] AC-4: `tests/test_pull_request_project_context.py` passes: the test asserts the Pre-Flight
  instruction is present in `templates/agents/pull-request.md` by scanning for the string
  `PROJECT_CONTEXT.md` within a section named `Pre-Flight`.

- [ ] AC-5: `tests/test_pull_request_project_context.py` passes: the test asserts
  `.agents/agents/pull-request/PROJECT_CONTEXT.md` exists on disk at the path resolved relative
  to the repo root.

- [ ] AC-6: `tests/test_pull_request_project_context.py` passes: the test asserts the context
  file body contains both the string `urlmonitor` (EMU guard) and the string `70` (title length
  limit).

## AC Coverage

| AC   | Test | Implementation | Validated |
|------|------|----------------|-----------|
| AC-1 |      |                |           |
| AC-2 |      |                |           |
| AC-3 |      |                |           |
| AC-4 |      |                |           |
| AC-5 |      |                |           |
| AC-6 |      |                |           |

## Implementation Notes

- The Pre-Flight step must be inserted **before** `## Step 0 — Remote Precondition Check` in
  `pull-request.md`, so it is the very first action the agent takes.
- The standard Pre-Flight wording (from the convention doc) is:

  > **Pre-Flight Step: Load PROJECT_CONTEXT**
  > Read `.agents/agents/pull-request/PROJECT_CONTEXT.md` if it exists. Follow every pointer
  > in that file (READMEs, how-tos, conventions) before proceeding. If the file is absent,
  > log one debug line (`PROJECT_CONTEXT.md not found for pull-request; running template-only`)
  > and continue with template-only behaviour.

- The `.agents/` directory does not yet exist in this repo. Create `.agents/agents/pull-request/`
  on first use (never pre-create empty directories).
- The EMU guard in `PROJECT_CONTEXT.md` should reference the existing CLAUDE.md Pre-Drive
  Checklist note for full context, and instruct the agent to automate what was previously manual.
- The test file goes in `tests/` (not `unit_tests/`), following the pattern of
  `tests/test_agent_registry.py` and similar wiring-verification tests in that directory.

## Related

- Feedback entry: `fb_2026-06-03_80dafa72` (pull-request phase exhausted adjudication ladder
  due to EMU block)
- Convention: `docs/conventions/PROJECT_CONTEXT-injection.md`
- How-to: `docs/how-to/inject-project-knowledge-into-agents.md`
- CLAUDE.md Pre-Drive Checklist (EMU account section)

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request
