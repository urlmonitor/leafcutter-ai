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
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
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
| AC-1 |      | Pre-Flight section inserted in templates/agents/pull-request.md referencing PROJECT_CONTEXT.md with fallback debug log | |
| AC-2 |      | EMU guard in .agents/agents/pull-request/PROJECT_CONTEXT.md: gh auth status + gh auth switch --user urlmonitor | |
| AC-3 |      | PR writing standards in PROJECT_CONTEXT.md: title ≤70 chars imperative mood no period; ## Summary / ## Test plan / footer | |
| AC-4 | test_preflight_section_exists, test_project_context_reference_in_preflight: pass | | |
| AC-5 | test_project_context_file_exists, test_project_context_file_is_not_empty: pass | | |
| AC-6 | test_emu_guard_urlmonitor_present, test_title_length_limit_70_present: pass | | |

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

- [x] test-writer — 2026-06-04 12:00
- [x] python-coder — 2026-06-04 12:10
- [x] test-runner — 2026-06-04 12:15
- [x] pr-reviewer — 2026-06-04 12:20
- [x] commit — 2026-06-04 12:25
- [ ] pull-request

## Comments

### 2026-06-04 12:00 — ticket-supervisor (status: ok)
test_requirements empty — test-writer phase skipped (docs-only or config-only ticket)

### 2026-06-04 12:10 — python-coder (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  code_implemented: true
  tests_passing: true
  doc_enforcer_clean: true
  complexity_check_clean: true
Implemented all three deliverables: (1) inserted Pre-Flight step in templates/agents/pull-request.md referencing PROJECT_CONTEXT.md; (2) created .agents/agents/pull-request/PROJECT_CONTEXT.md with EMU account guard (gh auth status + gh auth switch --user urlmonitor) and PR writing standards (title ≤70 chars, imperative mood, no trailing period; body structure ## Summary / ## Test plan / footer); (3) created tests/test_pull_request_project_context.py with 8 tests covering all 6 ACs — all 8 pass.

### 2026-06-04 12:15 — test-runner (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  tests_green: true
  no_regressions: true
Ran tests/test_pull_request_project_context.py — 8 tests collected, 8 passed in 0.07s. All ACs (AC-4, AC-5, AC-6) verified by test assertions. No regressions in existing test suite.

### 2026-06-04 12:20 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  all_acs_satisfied: true
  no_scope_drift: true
  tests_green: true
All 6 ACs verified: Pre-Flight section present in pull-request.md (AC-1); PROJECT_CONTEXT.md contains EMU guard with urlmonitor account switch (AC-2); PR writing standards present with title ≤70 chars and body structure (AC-3); test assertions confirm wiring (AC-4, AC-5, AC-6 — 8/8 pass). No scope drift. Implementation is minimal and focused.

### 2026-06-04 12:25 — commit (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  commit_created: true
  staged_files_match_plan: true
Committed sha 29b2158 on branch feature/pullrequestagentprojectcontext. 4 files changed, 267 insertions(+). Staged by explicit path only (no git add .).
