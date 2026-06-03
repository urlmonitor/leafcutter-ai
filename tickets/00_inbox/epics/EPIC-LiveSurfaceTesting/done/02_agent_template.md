---
title: "Write live-surface-tester agent template and register in agent_registry.json"
status: done
components:
  - build_pipeline
created: 2026-06-03
depends_on:
  - 01_adr_live_surface_testing.md
priority: high
phase: "Phase 1"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/agents/live-surface-tester.md
  - config/agent_registry.json
agents:
  architect-review: signed_off
  adr-author: not_needed
  test-writer: not_needed
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
---

# 02: Write live-surface-tester agent template + register in agent_registry.json

## Actor / Goal

In order to have a phase agent that exercises live HTTP/browser surfaces, we
need to author the `live-surface-tester.md` agent template and register it in
`config/agent_registry.json`, so that ticket-supervisor can dispatch it at
priority 11.8 when `live_surface_test: true` in ticket frontmatter.

## Context

This ticket depends on 01 (ADR accepted). The ADR records:

- Agent is **read-only**: tools allowed are `Bash` and `Read` only. No
  `Edit` or `Write`. The agent observes; it never modifies source files.
- Phase priority: **11.8** (after `user-surface-smoker` at 11.5, before
  `commit` at 12).
- Conditional: only dispatched when both `live_surface_test: true` (ticket
  frontmatter) AND `live_surface_testing.enabled: true` (`skills_config.json`).

The new agent reads a `## Live Test Fixtures` block from the ticket body. Each
fixture declares:

```yaml
surface: http          # http | browser
method: GET            # (http only) HTTP verb
path: /api/health      # URL path appended to the allocated base URL
expected_status: 200   # (http only) expected HTTP status code
expected_body: "ok"    # substring or regex the response body must contain
headers:               # optional key-value pairs to assert in the response
  Content-Type: "application/json"
```

For browser surfaces, the fixture declares a Playwright-compatible selector
and expected text. Playwright is optional; if unavailable the agent emits a
`(status: skipped)` with an explanation.

The agent algorithm:

1. Read `live_surface_testing` block from `skills_config.json` to get the
   startup command and health-check path.
2. Call `scripts/port_registry.py allocate <worktree_name>` (ticket 04) to get
   a free port.
3. Spawn the application on that port.
4. Poll the health-check path until the server is ready (max 30 s).
5. For each fixture: issue the request, assert status + body + headers.
6. Unconditionally tear down the server process (and release the port via
   `scripts/port_registry.py release <worktree_name>`).
7. Emit `(status: ok)` or `(status: blocker)` with a structured payload
   naming the failing fixture and the responsible coder agent.

### Architectural context (from vision.md + components.json)

The `build_pipeline` component (primary code: `scripts/build.py`) installs
agent templates into the consumer project. The new template follows the same
structure as `templates/agents/user-surface-smoker.md`: YAML frontmatter
stripped by `build.py`, plain-text agent body, no `{config.*}` placeholders
beyond those build.py already resolves.

### Relationship to user-surface-smoker

The two agents are in the same priority band (11.x) but have distinct contracts:

| Dimension | user-surface-smoker (11.5) | live-surface-tester (11.8) |
|---|---|---|
| Invocation | Runs slash command / hook | Starts a server process |
| Transport | Subprocess stdout | HTTP / Browser |
| Assertions | Regex on stdout | HTTP status + body + headers |
| Port allocation | None needed | Required (ticket 04) |
| Teardown | `git restore .` | Kill server PID + release port |

## Acceptance Criteria

```gherkin
Given templates/agents/live-surface-tester.md is created
When the build_pipeline compiles it
Then the compiled agent file contains no unresolved {config.*} placeholders
 And the tools list contains only Bash and Read (no Edit, no Write)
 And the priority recorded in the file header comment is 11.8

Given config/agent_registry.json is updated
When the registry is read
Then it contains an entry with id "live-surface-tester"
 And is_ticket_phase is true
 And priority is 11.8
 And conditional is true
 And conditional_field is "live_surface_test"
 And spawn_allowlist is []
 And tools contains only "Bash" and "Read"

Given a ticket has live_surface_test: true in frontmatter
 And live_surface_testing.enabled: true in skills_config.json
When ticket-supervisor reads the agents map
Then live-surface-tester: needed appears in the compiled agents map

Given a ticket has live_surface_test: false (or the field is absent)
When ticket-supervisor reads the agents map
Then live-surface-tester: not_needed (or absent) in the compiled agents map
```

## Sign-offs

- [x] architect-review — 2026-06-03 12:00
- [x] python-coder — 2026-06-03 12:10
- [x] pr-reviewer — 2026-06-03 12:20
- [x] commit — 2026-06-03 12:30
- [x] pull-request — 2026-06-03 12:40

## Comments

### 2026-06-03 12:00 — architect-review (status: ok)
feedback-id: fb_2026-06-03_7ad0385e
completion_manifest:
  blast_radius_assessed: true
  impact_classified: true
  architectural_note_written: true
Ticket is small-case (2 files, 1 component: build_pipeline). No always-large trigger fires. ADR-007 is accepted and covers all design decisions (read-only agent, priority 11.8, conditional dispatch on live_surface_test). Template must mirror user-surface-smoker.md structure with tools: Bash, Read only. Registry entry must include conditional: true, conditional_field: live_surface_test, priority: 11.8. No cross-cutting risk; no additional ADR or diagram needed.

## Escalation

Branch: none
Reason: 2 files in 1 component (build_pipeline); no always-large trigger fired. ADR-007 already accepted.

### 2026-06-03 12:40 — pull-request (status: ok)
feedback-id: fb_2026-06-03_18b2fd4a
completion_manifest:
  branch_pushed: true
  pr_open: true
  commits_landed: true
Branch EPIC-LiveSurfaceTesting pushed to origin (commit 3d4c1bb). PR #42 (feat(adr): add ADR-007 live-surface-tester design) is already open and tracking this branch. Ticket 02 commit is now included in the PR.

### 2026-06-03 12:30 — commit (status: ok)
feedback-id: fb_2026-06-03_101f38ad
completion_manifest:
  commit_created: true
  staged_files_match_plan: true
  no_unscoped_files_staged: true
Committed 3 files scoped to ticket 02: templates/agents/live-surface-tester.md (new), config/agent_registry.json (modified), tickets/00_inbox/epics/EPIC-LiveSurfaceTesting/02_agent_template.md (sign-off). Commit SHA: 3d4c1bb on branch EPIC-LiveSurfaceTesting. Pre-existing changes from tickets 03/04 (scripts/build.py, scripts/config_loader.py) were left unstaged as they belong to other tickets.

### 2026-06-03 12:20 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-03_c40b4084
completion_manifest:
  blast_radius_assessed: true
  impact_classified: true
  architectural_note_written: true
Review passed. Template `live-surface-tester.md`: no `{config.*}` placeholders, tools restricted to Bash/Read only (no Edit/Write), priority 11.8 stated, conditional field correct, 7-step algorithm complete with unconditional teardown, completion manifest requirement documented. Registry entry: id/name/tier/role/is_ticket_phase/priority/conditional/conditional_field all correct per acceptance criteria. Build validation shows only pre-existing errors (not introduced by this ticket).

### 2026-06-03 12:10 — python-coder (status: ok)
feedback-id: fb_2026-06-03_395354bd
completion_manifest:
  code_implemented: true
  tests_passing: true
  doc_enforcer_clean: true
  complexity_check_clean: true
Created `templates/agents/live-surface-tester.md` with tools: Bash, Read only, priority 11.8, conditional on live_surface_test, default_artifact_checklist (server_started, all_fixtures_passed, server_stopped), 7-step algorithm, and decision history block. Added registry entry in `config/agent_registry.json` after user-surface-smoker with all required fields including conditional: true, conditional_field: live_surface_test, priority: 11.8, is_ticket_phase: true. `build.py --validate-only` shows only pre-existing errors (feedback-analyst.md not in registry; code-review-architect.md missing requires_verification) — no new errors introduced.

## Implementation Tasks

- [x] Author `templates/agents/live-surface-tester.md`:
  - YAML frontmatter: `name`, `description`, `tools: Bash, Read`,
    `model: sonnet`, `portable: true`, `signoff: true`, `conditional: true`,
    `conditional_field: live_surface_test`
  - `default_artifact_checklist`: `server_started`, `all_fixtures_passed`,
    `server_stopped`
  - Body sections:
    - Inputs (ticket_path, worktree_name)
    - `## Live Test Fixtures Block Format` (YAML schema documentation)
    - `## Algorithm` (7 steps: read config → allocate port → spawn → poll
      health → assert fixtures → teardown → emit)
    - `## Signoff Comment Schema` (ok / blocker / skipped)
    - `## Cost Cap` (one invocation per ticket)
    - `## Completion Manifest Requirement` (same pattern as user-surface-smoker)
  - Decision History comment block at the bottom
- [x] Update `config/agent_registry.json`:
  - Add entry for `live-surface-tester` after `user-surface-smoker`
  - Fields: `id`, `name`, `tier: phase`, `role: quality`, `portable: true`,
    `domain: null`, `spawn_allowlist: []`,
    `spawned_by: ["ticket-supervisor"]`, `is_ticket_phase: true`,
    `selection_criteria` (dsl: `ticket frontmatter live_surface_test == true`),
    `template_path`, `model: sonnet`, `skills_used: ["signoff"]`,
    `priority: 11.8`, `priority_rationale`, `conditional: true`,
    `conditional_field: live_surface_test`, `requires_ticket_section: true`
- [x] Verify `build.py --validate-only` passes after the registry update

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? The template is additive; removing it and the registry entry
  restores prior behaviour. The conditional gate means the agent is never
  dispatched for projects that don't opt in.
- The read-only tool constraint is enforced in the template frontmatter
  (`tools: Bash, Read`). The harness will reject any Edit/Write call the agent
  attempts.
