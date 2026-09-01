---
title: "Configurable origin_agent defaults per agent and skill"
status: todo
components:
  - ac_store
created: 2026-06-05
depends_on:
  - 04_authorship_tracking.md
priority: low
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/commit_guardian/check_ac_schema.py
  - config/agent_registry.json
  - config/skill_registry.json
  - unit_tests/commit_guardian/test_check_ac_identity.py
agents:
  test-writer: needed
  python-coder: needed
  test-runner: needed
  pr-reviewer: needed
  commit: needed
  pull-request: not_needed
ac_coverage: 0/4
---

# 05: Configurable origin_agent defaults per agent and skill

## Actor / Goal

In order to avoid agents having to hard-code their own name when creating ACs,
we need a default origin_agent mechanism in agent templates and skill metadata
— so that the creating agent's identity is captured automatically and can be
overridden when needed.

## Context

Extends ticket 04 (authorship tracking). Currently agents set origin_agent
manually. This ticket adds a `default_origin_agent` field to agent_registry.json
and skill_registry.json, with a clear precedence chain: explicit value > template
default > agent's own registered name.

## AC References

- Implements ACS-100e-1 (agent template declares default origin_agent)
- Implements ACS-100e-2 (explicit value overrides template default)
- Implements ACS-100e-3 (skill metadata declares default for skill-created ACs)
- Implements ACS-100e-4 (missing default falls back to agent's own name)

## Acceptance Criteria

- [ ] AC-1: Agent registry entry with default_origin_agent field is used when agent creates an AC
- [ ] AC-2: Explicit origin_agent in AC creation call overrides the registry default
- [ ] AC-3: Skill registry entry with default_origin_agent is used for skill-created ACs
- [ ] AC-4: Agent with no default_origin_agent in registry uses its own registered name

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| ACS-100e-1 | | | |
| ACS-100e-2 | | | |
| ACS-100e-3 | | | |
| ACS-100e-4 | | | |

## Test Requirements

```yaml
tests:
  - path: unit_tests/commit_guardian/test_check_ac_identity.py
    covers: [ACS-100e-1, ACS-100e-2, ACS-100e-3, ACS-100e-4]
    type: unit
    rationale: "Precedence chain is independently testable per level"
```

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

- [ ] Add default_origin_agent field to agent_registry.json schema
- [ ] Add default_origin_agent field to skill_registry.json schema
- [ ] Implement resolution logic: explicit > template > name
- [ ] Write tests for the full precedence chain

## Risk & Safety

- Touches money? No
- Touches data? No — registry metadata only
- Reversibility? Field is optional; absence triggers fallback
