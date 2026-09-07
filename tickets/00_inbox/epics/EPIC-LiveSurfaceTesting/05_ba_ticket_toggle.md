---
title: "Teach business-analyst heuristics for live_surface_test frontmatter field"
status: todo
components:
  - build_pipeline
created: 2026-06-03
depends_on:
  - 01_adr_live_surface_testing.md
priority: medium
phase: "Phase 1"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/agents/business-analyst.md
  - config/agent_registry.json
agents:
  architect-review: not_needed
  adr-author: not_needed
  test-writer: not_needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
---

# 05: Teach business-analyst heuristics for live_surface_test frontmatter field

## Actor / Goal

In order to spare ticket authors from having to manually decide whether a ticket
warrants live surface testing, we need to add heuristic rules to the
`business-analyst` agent template that determine whether to emit
`live_surface_test: true` in the ticket frontmatter, so that docs-only,
config-only, and internal refactor tickets are automatically skipped.

## Context

This ticket depends on 01 (ADR accepted). The ADR defines the ticket-level
toggle: a frontmatter field `live_surface_test` (boolean). This ticket teaches
the BA agent to set it correctly.

### Heuristic rules (auto-skip when ANY is true)

The BA should set `live_surface_test: false` (opt out) when:

1. The ticket is docs-only (all `files_touched` are under `docs/`, with no
   code files).
2. The ticket is config-only (all `files_touched` are config JSON/YAML with no
   executable code).
3. The ticket is an internal refactor that does not change any HTTP endpoint,
   route handler, or UI component (BA judgment call).
4. The ticket touches only test files (`unit_tests/` or `test_*.py`) with no
   corresponding application code changes.
5. The ticket's `components` list does not include any component with a
   `primary_code` path that suggests a running server (no `api/`, `app/`,
   `server/`, `frontend/`, `views/`, `routes/` paths).
6. `live_surface_testing.enabled: false` in `skills_config.json` (project-wide
   opt-out; BA reads this via the context provided in its invocation prompt).

The BA should set `live_surface_test: true` (opt in) when:

- The ticket adds, modifies, or removes an HTTP endpoint (route handler, view,
  controller).
- The ticket changes authentication or authorization middleware.
- The ticket modifies CORS policy, rate limiting, or request validation.
- The ticket changes a frontend page or component that renders to a real browser
  URL.
- The ticket modifies the startup sequence, environment variable handling, or
  application factory.

### Frontmatter field spec

```yaml
live_surface_test: true   # or false; absent = same as false
```

The field is optional. The BA emits it only when it can confidently set it.
When the BA cannot determine (ambiguous ticket), it omits the field and emits
an open question asking the ticket author to decide.

### agent_registry.json update

The `business-analyst` entry's `selection_criteria` comment should note that it
considers `live_surface_test` heuristics. No structural schema change is needed.

### build.py / ticket-supervisor behavior

When `live_surface_test` is absent in the frontmatter, `ticket-supervisor`
treats it as `false`. The `live-surface-tester` agent is never dispatched for
tickets missing the field.

## Acceptance Criteria

```gherkin
Given a ticket request that is entirely docs-only (files_touched has only docs/*.md)
When the business-analyst processes the request
Then the output JSON contains live_surface_test: false

Given a ticket request that adds a new REST endpoint in api/routes/foo.py
When the business-analyst processes the request
Then the output JSON contains live_surface_test: true

Given a ticket request for an internal Python refactor (no route files touched)
When the business-analyst processes the request
Then the output JSON contains live_surface_test: false

Given live_surface_testing.enabled: false in skills_config.json
When the business-analyst processes any ticket request
Then the output JSON always contains live_surface_test: false
 (regardless of what the ticket touches)

Given an ambiguous ticket where the BA cannot determine surface exposure
When the business-analyst processes the request
Then live_surface_test is absent from the output JSON
 And an open question is emitted asking the ticket author to decide
```

## Sign-offs

- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit

## Comments

## Implementation Tasks

- [ ] Edit `templates/agents/business-analyst.md`:
  - Add a new `## Live Surface Test Heuristics` section (after the existing
    `## Default agents map by ticket archetype` section)
  - Document the 6 auto-skip rules and the 5 opt-in rules listed in Context
  - Update the output JSON schema example to include
    `"live_surface_test": true | false | null`
  - Add the heuristic evaluation step to the BA's algorithm section:
    "Before emitting the structured JSON, evaluate the live_surface_test
    heuristics. Emit the field when confident; emit an open question when
    ambiguous."
- [ ] Update the output JSON schema in the BA template:
  - Add `live_surface_test` to the `## Output Contract` section
  - Document it as optional: absent = false

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? The change is to an agent template. Rolling back is a
  `git revert` on the template file. Existing tickets are unaffected
  (the field is new and optional).
- False positives (BA sets `true` for a docs ticket): harmless — the
  `live-surface-tester` will attempt to start the server and immediately fail
  the health check if no server command is configured. The test fails gracefully
  with `(status: blocker)` and a clear message.
- False negatives (BA sets `false` for a ticket that adds an endpoint): the
  endpoint goes untested by the live surface gate. This is the same situation
  as before this epic. It does not regress existing behaviour.
