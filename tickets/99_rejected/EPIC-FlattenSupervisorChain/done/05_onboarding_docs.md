---
title: "Update onboarding wizard and docs for Claude Code Workflow version requirement"
status: done
components:
  - build_pipeline
created: 2026-06-01
depends_on:
  - 02_build_ticket_workflow.md
  - 03_build_epic_workflow.md
  - 04_create_ticket_workflow.md
priority: medium
phase: "Phase 1"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/agents/onboard.md
  - docs/how-to/
  - docs/reference/
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: signed_off
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: signed_off
  reference-author: not_needed
  user-surface-smoker: not_needed
user_facing_surface: null
requires_documentation:
  - how_to
---

# 05: Update onboarding wizard and docs for Claude Code Workflow version requirement

## Actor / Goal

In order to prevent new adopters from silently running a degraded installation
(agent-only path, no JS workflows), we need the onboarding wizard to check
the Claude Code version and warn clearly if it is below 2.1.154, and we need
reference docs that describe the workflow version requirement, token cost
implications, the no-mid-run-steering constraint, and the shell-command
allowlist configuration.

## Context

Claude Code Workflows are available since v2.1.154. Users on older versions
receive only the legacy supervisor agent path. Without documentation, they will
not understand why phase agents appear to silently skip in multi-level dispatch
scenarios.

This ticket covers four documentation deliverables:

1. **Onboard wizard check** — `templates/agents/onboard.md` emits a version
   check during onboarding and prints a clear warning if Claude Code < 2.1.154.
2. **Version requirement note** — brief note added to the onboard wizard output
   telling users what features require v2.1.154+.
3. **How-to guide** — `docs/how-to/configure-workflow-allowlist.md` documents
   how to configure the shell-command allowlist in `settings.json` to minimise
   permission prompts during workflow execution.
4. **Reference doc** — `docs/reference/workflow-constraints.md` documents:
   - Minimum version requirement (2.1.154) and how to verify.
   - Token cost implications (planner agent adds one extra call per ticket/epic/create).
   - No-mid-run-steering constraint (workflows run deterministically; there is
     no pause point for user input mid-run except via `prompt()`).
   - Crash resume behaviour (ticket-file state as the resume mechanism).

### Architectural context (from docs/vision.md)

The onboarding experience is part of the Phase 1 "self-onboarding" exit
criterion. The docs must be accurate and actionable without requiring users
to read the ADR or the JS source.

## Acceptance Criteria

```gherkin
Given a fresh install where CLAUDE_CODE_VERSION=1.9.0
When the onboarding wizard runs
Then the output contains a warning: "Claude Code >= 2.1.154 required for workflow scripts"
 And the warning explains which features are degraded (build-ticket, build-epic, create-ticket workflows)
 And the wizard does not abort — it continues onboarding with the legacy agent path noted

Given a fresh install where CLAUDE_CODE_VERSION=2.2.0
When the onboarding wizard runs
Then no version warning is emitted for workflows
 And the output notes "Workflow scripts will be installed (v2.2.0 >= 2.1.154)"

Given a user who wants to reduce permission prompts during workflow execution
When they read docs/how-to/configure-workflow-allowlist.md
Then they can find the recommended allowlist entries for git, gh, python, and npm commands
 And the guide explains where to place the allowlist (settings.json → allowedTools)
 And the guide explains the difference between allowedTools and dangerouslyAllowTools

Given a user asking about token costs
When they read docs/reference/workflow-constraints.md
Then they find a clear description of the planner-agent overhead per ticket
 And they find the no-mid-run-steering constraint described with a workaround (prompt())
 And they find the crash-resume mechanism described
```

## Sign-offs

- [x] documentation-expert — 2026-06-01 14:00
- [x] how-to-author — 2026-06-01 14:10
- [x] pr-reviewer — 2026-06-01 14:20
- [x] commit — 2026-06-01 14:30
- [x] pull-request — 2026-06-01 14:35

## Comments

### 2026-06-01 14:00 — documentation-expert (status: ok)
feedback-id: fb_2026-06-01_70137bdb
completion_manifest:
  doc_written: true
  cross_links_added: true
  diataxis_genre_correct: true
Updated `templates/agents/onboard.md` with Step 1b — Claude Code version check (>= 2.1.154 required, warning block + confirmation line). Created `docs/reference/workflow-constraints.md` covering minimum version, token cost implications, no-mid-run-steering constraint, and crash-resume mechanism. How-to guide (`docs/how-to/configure-workflow-allowlist.md`) is the responsibility of the how-to-author phase which follows.

### 2026-06-01 14:10 — how-to-author (status: ok)
feedback-id: fb_2026-06-01_699e58e6
completion_manifest:
  guide_written: true
  location_correct: true
  steps_validated: true
Created `docs/how-to/configure-workflow-allowlist.md` with Prerequisites, Steps 1–4 (locate settings.json, add allowlist entries, understand allowedTools vs dangerouslyAllowTools, verify), Verification section, and cross-references. Guide placed in `docs/how-to/` (general contributor audience). Cross-links to `docs/reference/workflow-constraints.md` and `templates/settings.json` added.

### 2026-06-01 14:20 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-01_d9eba6c3
completion_manifest:
  diff_reviewed: true
  no_high_findings: true
  scope_verified: true
No high-confidence findings. All four Acceptance Criteria satisfied: onboard.md Step 1b covers both version branches with correct warning block format; workflow-constraints.md covers version, token cost, no-mid-run-steering, and crash-resume; configure-workflow-allowlist.md covers allowedTools vs dangerouslyAllowTools, recommended entries, and settings.json placement. Note: ticket 06 files are in the working diff but are correctly scoped separately — commit phase must stage only ticket 05 files explicitly.

### 2026-06-01 14:30 — commit (status: ok)
feedback-id: fb_2026-06-01_3ef2b0dc
completion_manifest:
  staged_correct_files: true
  commit_succeeded: true
  lock_released: true
Staged 4 ticket-05-scoped files (templates/agents/onboard.md, docs/reference/workflow-constraints.md, docs/how-to/configure-workflow-allowlist.md, ticket file). Committed as bf20f11: 4 files changed, 458 insertions(+), 9 deletions(-). Commit lock acquired and released. Ticket 06 files correctly excluded from staging.

### 2026-06-01 14:35 — pull-request (status: ok)
feedback-id: fb_2026-06-01_f7b4e9d2
completion_manifest:
  pr_deferred_to_epic: true
Deferred to epic-level PR per leafcutter one-PR-per-epic convention. Changes are committed locally at bf20f11. The PR will be opened by /build-feature at epic completion.

## Implementation Tasks

### documentation-expert

- [x] Update `templates/agents/onboard.md`:
  - Add a version check step: detect `CLAUDE_CODE_VERSION` (or call `claude --version`).
  - If below 2.1.154: emit a prominently-formatted warning block (use markdown
    `> [!WARNING]` if supported) listing: version found, minimum required, and
    which workflow scripts will NOT be installed.
  - If >= 2.1.154: emit a brief confirmation line.
- [x] Create `docs/reference/workflow-constraints.md` covering:
  - Minimum version requirement and detection command.
  - Planner-agent token overhead (one extra LLM call per ticket drive start, per
    epic plan start, and per create-ticket invocation).
  - No-mid-run-steering: once a workflow starts, the JS script runs deterministically.
    User steering is only possible at `prompt()` checkpoints (currently: open-questions
    in create-ticket.js).
  - Crash resume: if a workflow crashes mid-run, re-running `/build-feature` with
    the same epic/ticket path picks up from the last non-done ticket (based on
    `agents:` frontmatter state).

### how-to-author

- [x] Create `docs/how-to/configure-workflow-allowlist.md`:
  - Explain that workflow sub-agents run in `acceptEdits` mode but shell
    commands still trigger permission prompts.
  - Show the recommended `settings.json` snippet (see ticket 07 for the
    canonical allowlist content — reference it rather than duplicating it).
  - Explain `allowedTools` vs `dangerouslyAllowTools` (only `allowedTools`
    scoped to specific commands is appropriate for the pre-approved list).
  - Note: the allowlist is per-project; add to `.claude/settings.json` in
    the target project root.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Documentation-only changes. Fully reversible.
- Dependency note: this ticket depends on tickets 02–04 being DRAFTED (not
  necessarily merged) so the documentation-expert can reference the actual
  workflow constraints accurately. It does not need to wait for them to be
  deployed.
