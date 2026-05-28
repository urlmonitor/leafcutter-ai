---
title: "Register frontend-coder in agent_registry.json and extend skills_config.default.json"
status: todo
components:
  - config_loader
created: 2026-05-28
depends_on:
  - 01_frontend_coder_agent_template.md
priority: high
requires_diagram: false
requires_adr: false
files_touched:
  - leafcutter-ai/config/agent_registry.json
  - leafcutter-ai/config/skills_config.default.json
agents:
  architect-review: needed
  python-coder: needed
  sql-coder: not_needed
  test-writer: needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 05: Register frontend-coder in agent_registry.json and extend skills_config.default.json

## Actor / Goal

In order for the ticket pipeline to route frontend tasks to `frontend-coder` automatically, we need to register the agent in `agent_registry.json` with selection criteria and add the corresponding config keys to `skills_config.default.json`.

## Context

`agent_registry.json` is the single source of truth for all ticket-phase agents. Each entry specifies `id`, `is_ticket_phase`, `default_status`, `requires_ticket_section`, and `selection_criteria` (with `trigger_conditions`). The `business-analyst` and `refinement` agents read this registry to assign agents to tickets.

`frontend-coder` must be registered with:
- `is_ticket_phase: true`
- `requires_ticket_section: true` (like python-coder — it has a concrete task list under `## Implementation Tasks`)
- `default_status: "not_needed"` (same as sql-coder — only activated when the ticket explicitly touches frontend code)
- `selection_criteria.trigger_conditions`:
  - `files_touched` contains `*.html`, `*.tsx`, `*.jsx`, `*.vue`, `*.svelte`, `*.css`, `*.scss`
  - LLM expression: "ticket involves creating or modifying frontend/UI components, markup, or styles"
  - LLM expression: "ticket requires visual changes to a web interface"

`skills_config.default.json` needs new keys for frontend-coder configuration:
- `frontend.project_context_path`: path to `PROJECT_CONTEXT.md` for the frontend-coder agent (default: `.agents/agents/frontend-coder/PROJECT_CONTEXT.md`)
- `frontend.optional_skills`: list of installed optional skill names (default: `[]`)
- `frontend.test_command`: command to run the frontend test suite after changes (default: `""`)

The `build.py` script should pass `frontend.project_context_path` into the rendered `frontend-coder.md` agent template so the agent knows where to look for project context.

## Acceptance Criteria

```gherkin
Given the agent_registry.json is updated with a frontend-coder entry
When build.py validates the registry
Then no validation errors are reported
And frontend-coder appears in the registry with is_ticket_phase: true and selection_criteria

Given a business-analyst processes a ticket that touches a .tsx file
When it reads the agent_registry.json
Then it sets frontend-coder: needed in the agents map

Given skills_config.default.json is updated with frontend keys
When a new adopter runs /onboard
Then the wizard offers to configure frontend.project_context_path and frontend.optional_skills

Given build.py is run after adding the frontend-coder entry
When it renders frontend-coder.md
Then the PROJECT_CONTEXT.md path is injected from skills_config.frontend.project_context_path
```

## Sign-offs

- [ ] architect-review
- [ ] python-coder
- [ ] test-writer
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### python-coder

- [ ] Edit `leafcutter-ai/config/agent_registry.json`: add a `frontend-coder` entry object after the `sql-coder` entry, with fields: `id: "frontend-coder"`, `is_ticket_phase: true`, `requires_ticket_section: true`, `default_status: "not_needed"`, `selection_criteria` with `description` and `trigger_conditions` (three entries: DSL expression for frontend file extensions, and two LLM expressions for UI/visual change tasks). Follow the exact JSON schema pattern of the `sql-coder` entry.
- [ ] Edit `leafcutter-ai/config/skills_config.default.json`: add a `frontend` object key with three nested keys: `project_context_path` (default: `".agents/agents/frontend-coder/PROJECT_CONTEXT.md"`), `optional_skills` (default: `[]`), `test_command` (default: `""`).
- [ ] Verify `build.py` already handles nested config keys (i.e. `frontend.project_context_path` is accessible as `{{frontend.project_context_path}}` in templates) — if not, add support in `scripts/build.py` for nested key expansion.

### test-writer

- [ ] Write a unit test `leafcutter-ai/tests/test_agent_registry.py::test_frontend_coder_registered` that loads `agent_registry.json` and asserts: `frontend-coder` entry exists, `is_ticket_phase` is True, `requires_ticket_section` is True, `selection_criteria` is non-null with at least one trigger condition.
- [ ] Write a unit test `leafcutter-ai/tests/test_skills_config_defaults.py::test_frontend_keys_present` that loads `skills_config.default.json` and asserts the `frontend` key exists with `project_context_path`, `optional_skills`, and `test_command` sub-keys.

## Risk & Safety

- Touches money? No.
- Touches data? No — config JSON edits only.
- Reversibility? Fully reversible by removing the added JSON entries.
- Shared contract? `agent_registry.json` is read by `business-analyst`, `refinement`, and `create-epic` at runtime. Adding a new entry is backward-compatible. The `selection_criteria` for `frontend-coder` must not overlap ambiguously with `python-coder`'s criteria — a ticket touching a `.py` file that imports a frontend library should not trigger `frontend-coder`. The DSL expression scoped to frontend file extensions (`.tsx`, `.jsx`, `.vue`, `.svelte`, `.html`, `.css`, `.scss`) provides the necessary disambiguation.
