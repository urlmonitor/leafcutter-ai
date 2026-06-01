---
title: "EPIC: Frontend Agent"
type: epic
status: done
components:
  - build_pipeline
created: 2026-05-28
depends_on: []
priority: high
requires_diagram: false
requires_adr: true
---

# EPIC: Frontend Agent

Add a `frontend-coder` agent to the leafcutter-ai package, with optional `webapp-testing` and `frontend-design` skills, onboarding wizard integration, config extensibility, project-context support, and BA/supervisor routing so frontend/UI implementation tasks can be dispatched through the standard ticket pipeline.

## Key Design Decisions

### 1. frontend-coder is a first-class sibling implementation agent

**Decision:** `frontend-coder` is a peer to `python-coder` and `sql-coder` — a top-level implementation-phase agent with its own template, registry entry, and dispatch slot. It is NOT a sub-agent of `python-coder`.

**Rationale:** Symmetry with the existing coder pattern. Sub-agent nesting would breach the depth-3 agent cap and complicate the dispatch loop. Frontend work has distinct file types, conventions, and tooling that justify a dedicated agent rather than overloading `python-coder` with frontend concerns.

### 2. Optional-skill integration uses file-existence detection

**Decision:** `frontend-coder` detects installed optional skills (`webapp-testing`, `frontend-design`) by checking whether the skill's `SKILL.md` file exists at the expected path (e.g. `.claude/skills/webapp-testing/SKILL.md`). No registry lookup is needed.

**Rationale:** File-existence checks are the simplest mechanism, require zero infrastructure, and match how skills are already deployed by `build.py`. A registry-based mechanism would add coupling for no benefit — if the skill directory exists, the skill is installed.

### 3. Priority slot: frontend-coder dispatches at priority 8

**Decision:** `ticket-supervisor` dispatches `frontend-coder` at priority 8, between `sql-coder` (7) and `test-runner` (9).

**Rationale:** Frontend implementation should complete before tests run (test-runner needs the implementation to exist), and after SQL work (database schema changes may inform the frontend). This mirrors the sql-coder → test-runner ordering.

### 4. Single epic PR convention applies

**Decision:** All 6 tickets merge via one epic-branch PR (`EPIC-FrontendAgent` → `main`). Individual tickets commit to the epic branch but do not open separate PRs.

**Rationale:** Standard leafcutter epic convention. The 6 tickets have tight coupling (agent template → registry → routing) and shipping them atomically avoids broken intermediate states.

## Sub-Tickets

| # | File | Description | Status |
|---|------|-------------|--------|
| 01 | [01_frontend_coder_agent_template.md](./01_frontend_coder_agent_template.md) | Author the frontend-coder agent template following the python-coder/sql-coder pattern | `[ ]` |
| 02 | [02_webapp_testing_optional_skill.md](./02_webapp_testing_optional_skill.md) | Author the webapp-testing skill template (Playwright-based screenshot, console log, interaction) | `[ ]` |
| 03 | [03_frontend_design_optional_skill.md](./03_frontend_design_optional_skill.md) | Author the frontend-design skill template (bold, distinctive design guidance) | `[ ]` |
| 04 | [04_onboard_wizard_integration.md](./04_onboard_wizard_integration.md) | Add optional-skill prompts for webapp-testing and frontend-design to the onboard wizard | `[ ]` |
| 05 | [05_agent_registry_and_skills_config_extensibility.md](./05_agent_registry_and_skills_config_extensibility.md) | Register frontend-coder in agent_registry.json and add config keys to skills_config.default.json | `[ ]` |
| 06 | [06_ba_and_supervisor_routing_updates.md](./06_ba_and_supervisor_routing_updates.md) | Add frontend-coder to the BA archetype table and ticket-supervisor routing logic | `[ ]` |
