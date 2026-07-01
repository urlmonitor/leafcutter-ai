---
title: "Add workflows.enabled + workflows.engine to config schema and defaults"
status: todo
components:
  - build_pipeline
created: 2026-07-01
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
files_touched:
  - config/skills_config.schema.json
  - config/skills_config.default.json
  - unit_tests/test_workflows_config_keys.py
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
---

# 01: Add workflows.enabled + workflows.engine to config schema and defaults

## Actor / Goal

In order to select which workflow-engine variant the build deploys, we need
`workflows.enabled` and `workflows.engine` to be first-class, schema-validated
config keys so `build.py` can read them without a KeyError and consumers can
override the engine explicitly.

## Context

`build_phases.py` already *reads* `config["workflows"]["enabled"]` but the key
is absent from both `config/skills_config.schema.json` and
`config/skills_config.default.json` (a latent gap). This ticket closes that gap
and adds `workflows.engine` (`auto | e1 | e2`) which ticket 04's transform and
ticket 07's default-flip depend on. Config-only; no engine behaviour changes here.

## Acceptance Criteria

```gherkin
Scenario: schema accepts the new keys
  Given config/skills_config.schema.json
  When it is loaded as JSON Schema
  Then it defines a "workflows" object property with "enabled" (boolean)
   and "engine" (enum: auto, e1, e2)
  And the schema still validates the existing default config without error.

Scenario: defaults carry safe values
  Given config/skills_config.default.json
  Then it contains workflows.enabled (boolean) and workflows.engine == "auto"
  And the file remains valid JSON.

Scenario: build reads engine without KeyError
  Given the default config
  When build_phases.py reads config["workflows"]["engine"]
  Then it resolves to "auto" and does not raise.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |

## Comments

## Implementation Tasks
- [ ] Add `workflows` object (enabled: boolean, engine: enum auto/e1/e2) to skills_config.schema.json
- [ ] Add `workflows.enabled` + `workflows.engine: auto` to skills_config.default.json
- [ ] Add unit test asserting schema validity, default values, and no-KeyError read
- [ ] Confirm `build.py --validate-only` still passes

## Risk & Safety
- Touches money? No.
- Touches data? No — config schema + defaults only. Reversible.
