---
title: "Register frontend-coder in agent_registry.json and extend skills_config.default.json"
status: done
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
  architect-review: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-writer: signed_off
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
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

- [x] architect-review — 2026-05-28 12:30
- [x] python-coder — 2026-05-28 12:45
- [x] test-writer — 2026-05-28 12:50
- [x] test-runner — 2026-05-28 12:55
- [x] pr-reviewer — 2026-05-28 13:00
- [x] commit — 2026-05-28 13:05
- [x] pull-request — 2026-05-28 13:05

## Comments

### 2026-05-28 12:30 — architect-review (status: ok)
feedback-id: fb_2026-05-28_9c771cd0
Classified as SMALL: 2 JSON config files, 1-2 components (config_loader, build_pipeline), no always-large triggers. Adding a new agent_registry.json entry is backward-compatible. The selection_criteria DSL expression scoped to frontend extensions avoids overlap with python-coder criteria. Test tasks are well-defined in the ticket spec.

### 2026-05-28 12:45 — python-coder (status: ok)
feedback-id: fb_2026-05-28_92c158a7
Added frontend-coder entry to config/agent_registry.json after sql-coder (priority 8, is_ticket_phase=true, requires_ticket_section=true, default_status=not_needed, 3 trigger conditions, owns_file_extensions). Added frontend key to config/skills_config.default.json (project_context_path, optional_skills=[], test_command=""). Added _flatten_nested_keys() to scripts/config_loader.py to support dot-notation placeholder resolution ({{frontend.project_context_path}} resolves correctly). No changes to build.py itself — flattening happens at config load time in config_loader.py.

### 2026-05-28 12:50 — test-writer (status: ok)
feedback-id: fb_2026-05-28_8f1a0fab
Wrote tests/test_agent_registry.py (9 tests: frontend-coder exists, is_ticket_phase, requires_ticket_section, default_status=not_needed, selection_criteria non-null, trigger conditions non-empty, priority=8, DSL trigger includes frontend extensions, owns_file_extensions). Wrote tests/test_skills_config_defaults.py (11 tests: frontend key present, all 3 sub-keys present, default values correct, load_config flattens to dot-notation, project override propagates). All 20 pass.

### 2026-05-28 12:55 — test-runner (status: ok)
feedback-id: fb_2026-05-28_74e5a27d
Ran: python3 -m pytest tests/test_agent_registry.py tests/test_skills_config_defaults.py -v — 20 passed in 4.75s. Regression check: python3 -m pytest tests/test_config_loader_output_root.py -v — 5 passed in 2.38s. All green, no regressions.

### 2026-05-28 13:00 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-28_32e605b1
Reviewed all deliverables: agent_registry.json entry valid JSON, backward-compatible, priority=8, DSL expression scoped to frontend extensions only (no python-coder overlap risk), is_ticket_phase=true, requires_ticket_section=true. skills_config.default.json well-formed with frontend key. config_loader.py _flatten_nested_keys correctly handles nested dicts with dot-notation and preserves original nested dict. 20 tests pass, 5 existing tests pass. All acceptance criteria verified.

### 2026-05-28 13:05 — commit (status: ok)
feedback-id: fb_2026-05-28_5300376a
Committed in batch 2 SHA 711f151. Epic-branch-only, no per-ticket PR.

### 2026-05-28 13:05 — pull-request (status: ok)
feedback-id: (submit-failed)
Single-PR-per-epic convention: no per-ticket PR. PR opened at epic completion.

## Implementation Tasks

### python-coder

- [x] Edit `leafcutter-ai/config/agent_registry.json`: add a `frontend-coder` entry object after the `sql-coder` entry, with fields: `id: "frontend-coder"`, `is_ticket_phase: true`, `requires_ticket_section: true`, `default_status: "not_needed"`, `selection_criteria` with `description` and `trigger_conditions` (three entries: DSL expression for frontend file extensions, and two LLM expressions for UI/visual change tasks). Follow the exact JSON schema pattern of the `sql-coder` entry.
- [x] Edit `leafcutter-ai/config/skills_config.default.json`: add a `frontend` object key with three nested keys: `project_context_path` (default: `".agents/agents/frontend-coder/PROJECT_CONTEXT.md"`), `optional_skills` (default: `[]`), `test_command` (default: `""`).
- [x] Verify `build.py` already handles nested config keys (i.e. `frontend.project_context_path` is accessible as `{{frontend.project_context_path}}` in templates) — if not, add support in `scripts/build.py` for nested key expansion.

### test-writer

- [x] Write a unit test `leafcutter-ai/tests/test_agent_registry.py::test_frontend_coder_registered` that loads `agent_registry.json` and asserts: `frontend-coder` entry exists, `is_ticket_phase` is True, `requires_ticket_section` is True, `selection_criteria` is non-null with at least one trigger condition.
- [x] Write a unit test `leafcutter-ai/tests/test_skills_config_defaults.py::test_frontend_keys_present` that loads `skills_config.default.json` and asserts the `frontend` key exists with `project_context_path`, `optional_skills`, and `test_command` sub-keys.

## Risk & Safety

- Touches money? No.
- Touches data? No — config JSON edits only.
- Reversibility? Fully reversible by removing the added JSON entries.
- Shared contract? `agent_registry.json` is read by `business-analyst`, `refinement`, and `create-epic` at runtime. Adding a new entry is backward-compatible. The `selection_criteria` for `frontend-coder` must not overlap ambiguously with `python-coder`'s criteria — a ticket touching a `.py` file that imports a frontend library should not trigger `frontend-coder`. The DSL expression scoped to frontend file extensions (`.tsx`, `.jsx`, `.vue`, `.svelte`, `.html`, `.css`, `.scss`) provides the necessary disambiguation.
