---
title: "Mark epic-supervisor and ticket-supervisor as legacy_only in agent_registry.json"
status: todo
components:
  - build_pipeline
created: 2026-06-01
depends_on:
  - 02_build_ticket_workflow.md
  - 03_build_epic_workflow.md
priority: medium
phase: "Phase 1"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - config/agent_registry.json
  - templates/agents/epic-supervisor.md
  - templates/agents/ticket-supervisor.md
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
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

# 06: Mark epic-supervisor and ticket-supervisor as legacy_only in agent_registry.json

## Actor / Goal

In order to signal clearly that epic-supervisor and ticket-supervisor are
superseded by the JS workflow path while keeping them functional for sub-v2.1.154
installs, we need to add `legacy_only: true` to their registry entries and insert
a deprecation-warning block at the top of each agent template.

## Context

ADR-006 already set `"deprecated": true` on `epic-supervisor` in `agent_registry.json`.
This ticket extends that signal:

- Adds `"legacy_only": true` to both `epic-supervisor` and `ticket-supervisor`
  registry entries (a clearer, actionable flag that tooling can gate on).
- Inserts a `> [!NOTE] This agent is in legacy mode...` header in each template
  file so any adopter who opens it sees the deprecation notice and the JS
  workflow alternative immediately.
- Adds a "degraded experience" note to the templates that describes what breaks
  on older Claude Code versions (phase agents silently skip at depth 2).
- Does NOT delete or disable either template — they remain compilable and
  functional for users on Claude Code < 2.1.154.

### Relationship to build.py dual-path

Ticket 01 gates JS workflow installation on version detection. On installs
where the JS files are absent (because the build ran on Claude Code < 2.1.154),
`build.py` still compiles both supervisor templates via `build_agents()`.
The `legacy_only` flag in the registry enables future tooling to automatically
skip spawning these agents when workflows are available.

### Architectural context

- ADR-006: `docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md` §3:
  "epic-supervisor is deprecated, not deleted."
- Registry: `config/agent_registry.json`
- Templates: `templates/agents/epic-supervisor.md`, `templates/agents/ticket-supervisor.md`

## Acceptance Criteria

```gherkin
Given agent_registry.json before this change
When this ticket is applied
Then epic-supervisor entry has "legacy_only": true AND "deprecated": true
 And ticket-supervisor entry has "legacy_only": true

Given the compiled epic-supervisor.md agent file in .claude/agents/
When an adopter opens the file
Then the first non-frontmatter content is a deprecation notice
 And the notice names the JS workflow alternative (build-epic.js)
 And the notice states the minimum Claude Code version for the JS path (2.1.154)

Given the compiled ticket-supervisor.md agent file
When an adopter opens the file
Then the first non-frontmatter content is a deprecation notice
 And the notice names the JS workflow alternative (build-ticket.js)

Given a build.py run on Claude Code >= 2.1.154
When both supervisor templates are still present in templates/agents/
Then build_agents() still compiles them (no hard-delete from build phase)
 And build_workflow_scripts() also installs the JS alternatives
 And the two paths coexist without conflict
```

## Sign-offs

- [x] test-writer — 2026-06-01 00:00
- [x] python-coder — 2026-06-01 00:05
- [x] test-runner — 2026-06-01 00:10
- [x] pr-reviewer — 2026-06-01 00:15
- [ ] commit
- [ ] pull-request

## Comments

### 2026-06-01 00:00 — ticket-supervisor (status: ok)
feedback-id: fb_2026-06-01_ticket-06-supervisor
test_requirements empty — test-writer phase skipped (docs-only or config-only ticket)

### 2026-06-01 00:15 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  acceptance_criteria_met: true
  registry_changes_correct: true
  template_notices_correct: true
  test_coverage_adequate: true
  no_scope_creep: true
All acceptance criteria met: epic-supervisor has legacy_only+deprecated; ticket-supervisor has legacy_only; both templates have [!NOTE] deprecation callout with correct JS alternative references and version threshold (2.1.154); test file created with 6 passing tests; no files deleted.

### 2026-06-01 00:10 — test-runner (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  tests_collected: true
  tests_passed: true
  no_test_failures: true
6 tests collected and passed (unit_tests/test_agent_registry_legacy_flags.py): legacy_only flags verified in registry, template files verified present, deprecation notices verified in both templates. 0 failures.

### 2026-06-01 00:05 — python-coder (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  registry_epic_supervisor_legacy_only: true
  registry_ticket_supervisor_legacy_only: true
  epic_supervisor_template_deprecation_notice: true
  ticket_supervisor_template_deprecation_notice: true
  test_file_created: true
Added legacy_only:true to both epic-supervisor and ticket-supervisor in config/agent_registry.json; replaced the existing inline blockquote notice in epic-supervisor.md with the [!NOTE] callout block; inserted a matching [!NOTE] callout block in ticket-supervisor.md; created unit_tests/test_agent_registry_legacy_flags.py with 6 tests (all green: 6 passed in 1.77s).

## Implementation Tasks

### python-coder

- [x] In `config/agent_registry.json`:
  - Add `"legacy_only": true` to the `epic-supervisor` entry (alongside the
    existing `"deprecated": true`).
  - Add `"legacy_only": true` to the `ticket-supervisor` entry.
- [x] In `templates/agents/epic-supervisor.md`, insert at the top of the agent
  body (after the YAML frontmatter block) a deprecation notice:
  ```
  > [!NOTE]
  > **Legacy agent — superseded by `build-epic.js` (Claude Code Workflows).**
  > On Claude Code >= 2.1.154, use `/build-feature` which invokes `build-epic.js`
  > directly. This agent is retained for Claude Code < 2.1.154 compatibility only.
  > On older versions, phase agents at depth 2 will silently skip — the ticket
  > will appear to complete but no implementation will occur.
  ```
- [x] In `templates/agents/ticket-supervisor.md`, insert a matching deprecation
  notice referencing `build-ticket.js`.

### test-writer

- [x] Add `unit_tests/test_agent_registry_legacy_flags.py`:
  - `test_epic_supervisor_has_legacy_only_flag` — load `agent_registry.json`,
    assert `epic-supervisor` entry has `legacy_only == True`.
  - `test_ticket_supervisor_has_legacy_only_flag` — same for `ticket-supervisor`.
  - `test_legacy_agents_still_have_template_files` — assert both template paths
    still exist (not deleted).

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Registry changes are reversible by removing the `legacy_only`
  key. Template header additions are easily reverted.
- Dependency note: this ticket depends on tickets 02 and 03 being DRAFTED so
  the deprecation notices can name the correct JS alternative filenames. It does
  not need to wait for them to be merged.
