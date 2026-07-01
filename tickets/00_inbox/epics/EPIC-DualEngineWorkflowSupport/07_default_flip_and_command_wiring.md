---
title: "Default engine to E2, version-as-floor, wire command bodies to Workflow tool"
status: todo
components:
  - skills_system
  - build_pipeline
created: 2026-07-01
depends_on:
  - 05_port_build_epic_and_build_ticket.md
  - 06_port_plan_feature_and_finalize_feature.md
priority: high
requires_diagram: false
requires_adr: false
files_touched:
  - config/skills_config.default.json
  - scripts/build_phases.py
  - templates/commands/plan-feature.md
  - templates/commands/finalize-feature.md
  - templates/commands/build-feature.md
  - templates/commands/create-ticket.md
agents:
  architect-review: not_needed
  test-writer: needed
  llm-expert: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 07: Default engine to E2, version-as-floor, wire command bodies

## Actor / Goal

In order to make the deterministic workflow the sole path for users, we flip the
default engine to E2, demote the version check to a floor (not an engine selector),
and rewrite the command bodies to invoke the Workflow tool unconditionally — with
NO LLM prose fallback.

## Context

Final phase. With all scripts ported (05/06) and the transform in place (04), the
`auto` engine should resolve to E2 by default, and the command surfaces
(`plan-feature.md`, `finalize-feature.md`, `build-feature.md`, `create-ticket.md`)
must stop bailing to an "upgrade Claude Code" error / prose fallback and instead
invoke the workflow deterministically, failing loudly if the Workflow tool is
absent. `/create-ticket` (retired, ADR-012) routes to `/plan-feature` + `/build-ac`
instead of an upgrade nag. Removing `/build-feature`'s LLM fallback is the point
where the determinism liability is closed.

## Acceptance Criteria

```gherkin
Scenario: auto resolves to E2
  Given workflows.engine == "auto"
  When build_workflow_scripts resolves the target engine
  Then it selects E2, and the Claude Code version check is used only as a floor
   (below-min warns/skips) and NOT to pick the contract.

Scenario: command bodies invoke deterministically
  Given plan-feature.md, finalize-feature.md, build-feature.md
  Then each instructs invoking the corresponding workflow via the Workflow tool as
   the SOLE path, with no LLM prose fallback and a loud failure if unavailable.

Scenario: create-ticket routes, not nags
  Given create-ticket.md
  Then it routes the user to /plan-feature + /build-ac (per ADR-012) and does not
   print an "upgrade Claude Code" message.

Scenario: no residual LLM fallback
  Then build-feature.md no longer contains an inline prose batching fallback.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |

## Comments

## Implementation Tasks
- [ ] Set workflows.engine default resolution: auto -> e2; version check becomes floor-only in build_phases.py
- [ ] Rewrite plan-feature.md / finalize-feature.md / build-feature.md to invoke the Workflow tool as sole path (fail loud, no LLM fallback)
- [ ] Rewrite create-ticket.md to route to /plan-feature + /build-ac
- [ ] Remove build-feature.md inline prose batching fallback
- [ ] Tests: engine resolves to e2 under auto; command bodies contain no fallback markers

## Risk & Safety
- Touches money? No.
- Touches data? Command surfaces + build resolution. Removing the /build-feature fallback means an environment lacking the Workflow tool will fail loudly rather than improvise — that is the intended, safer behaviour. Reversible via git.
