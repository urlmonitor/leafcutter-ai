---
title: "Add live_surface_testing config block to skills_config.json schema and build.py injection"
status: todo
components:
  - config_loader
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
  - scripts/config_loader.py
  - scripts/build.py
  - templates/skills_config.json
  - docs/reference/skills_config_reference.md
agents:
  architect-review: needed
  adr-author: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: needed
  user-surface-smoker: not_needed
requires_documentation:
  - reference
---

# 03: Add live_surface_testing config block to skills_config.json schema + build.py injection

## Actor / Goal

In order to let projects opt in or out of live surface testing without touching
agent templates, we need to add a `live_surface_testing` block to
`skills_config.json` (with validation in `config_loader.py`) and wire it into
`build.py`'s template injection pipeline, so that compiled agent files receive
the correct conditional gate value.

## Context

This ticket depends on 01 (ADR accepted). The project-level toggle is:

```json
{
  "live_surface_testing": {
    "enabled": false,
    "startup_command": "python -m uvicorn app.main:app --host 0.0.0.0 --port {port}",
    "health_check_path": "/health",
    "startup_timeout_seconds": 30,
    "port_range_start": 8200,
    "port_range_end": 8299
  }
}
```

Key design points:

- **`enabled: false` is the safe default.** Pure library or CLI projects must
  not accidentally spin up servers during the ticket lifecycle.
- **`startup_command`** uses a `{port}` placeholder that the port registry
  (ticket 04) substitutes at runtime. This allows the same command template to
  work across concurrent worktrees on different ports.
- **`port_range_start` / `port_range_end`** define the project-specific port
  band. The port registry draws from this range. Default: 8200–8299 (100 ports,
  comfortably above the common dev range of 8000–8199).
- **`health_check_path`**: the path the startup helper polls to determine
  readiness. Default: `/health`.
- **`startup_timeout_seconds`**: max wait for the health check. Default: 30.

### config_loader.py changes

`config_loader.py` should:

1. Recognise `live_surface_testing` as a known optional key (not warn on it).
2. Validate that `enabled` is a bool when present.
3. Validate that `port_range_start < port_range_end` when present.
4. When `enabled: true`, validate that `startup_command` is a non-empty string.

### build.py injection

`build.py`'s `{{config.live_surface_testing.enabled}}` injection must be
available to agent templates. This is the same injection mechanism already used
for `{{config.workflows.enabled}}`. No new injection mechanism needed — extend
the existing config tree resolution.

### Template default

The `templates/skills_config.json` skeleton (written during `/onboard`) should
include the `live_surface_testing` block commented out, so adopters see it but
don't accidentally enable it.

### Reference doc update

`docs/reference/skills_config_reference.md` (if it exists) should gain a new
row for `live_surface_testing.*` fields. If the reference doc does not yet exist,
the `reference-author` sign-off creates it as part of this ticket.

## Acceptance Criteria

```gherkin
Given skills_config.json contains live_surface_testing.enabled: false
When config_loader.py validates it
Then no warnings or errors are emitted

Given skills_config.json contains live_surface_testing.enabled: true
 But startup_command is absent or empty
When config_loader.py validates it
Then it raises ConfigValidationError with message containing "startup_command"

Given skills_config.json contains port_range_start: 8300, port_range_end: 8200
When config_loader.py validates it
Then it raises ConfigValidationError with message containing "port_range"

Given skills_config.json has live_surface_testing.enabled: false
When build.py compiles the live-surface-tester template
Then the compiled agent contains the resolved value "false" for enabled
 And the compiled agent file is written without template injection errors

Given templates/skills_config.json is reviewed
When the live_surface_testing block is read
Then it is present but commented out
 And the comment explains it is optional and defaults to disabled
```

## Sign-offs

- [ ] architect-review
- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] reference-author
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

- [ ] Update `config_loader.py`:
  - Add `live_surface_testing` to the known-keys allowlist (no spurious
    unknown-key warning)
  - Add `_validate_live_surface_testing(config)` helper:
    - `enabled` must be bool when present
    - When `enabled: true`: `startup_command` must be a non-empty string
    - `port_range_start < port_range_end` (when both present)
  - Call the validator from the main `validate()` function
- [ ] Update `scripts/build.py`:
  - Ensure `config.live_surface_testing` subtree is included in the config
    object passed to the template renderer (extend the existing
    `config_to_template_vars()` function or equivalent)
- [ ] Update `templates/skills_config.json`:
  - Add the `live_surface_testing` block after the `workflows` block,
    commented out with a `// disabled by default — set enabled: true for
    projects with a running server` comment
- [ ] Update or create `docs/reference/skills_config_reference.md`:
  - Add `live_surface_testing` section covering all five keys, their types,
    defaults, and validation rules
- [ ] Write unit tests in `leafcutter-ai/tests/`:
  - `test_config_loader_live_surface_testing.py`:
    - `test_valid_disabled_config()`
    - `test_valid_enabled_config()`
    - `test_enabled_missing_startup_command()`
    - `test_port_range_inverted()`

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Config changes are backward compatible — the key is optional.
  Existing `skills_config.json` files that omit `live_surface_testing` continue
  to work unchanged (config_loader treats absence as `enabled: false`).
