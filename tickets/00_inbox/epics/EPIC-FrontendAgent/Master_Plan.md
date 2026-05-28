---
title: "EPIC: Frontend Agent"
type: epic
status: todo
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

## Sub-Tickets

| # | File | Description | Status |
|---|------|-------------|--------|
| 01 | [01_frontend_coder_agent_template.md](./01_frontend_coder_agent_template.md) | Author the frontend-coder agent template following the python-coder/sql-coder pattern | `[ ]` |
| 02 | [02_webapp_testing_optional_skill.md](./02_webapp_testing_optional_skill.md) | Author the webapp-testing skill template (Playwright-based screenshot, console log, interaction) | `[ ]` |
| 03 | [03_frontend_design_optional_skill.md](./03_frontend_design_optional_skill.md) | Author the frontend-design skill template (bold, distinctive design guidance) | `[ ]` |
| 04 | [04_onboard_wizard_integration.md](./04_onboard_wizard_integration.md) | Add optional-skill prompts for webapp-testing and frontend-design to the onboard wizard | `[ ]` |
| 05 | [05_agent_registry_and_skills_config_extensibility.md](./05_agent_registry_and_skills_config_extensibility.md) | Register frontend-coder in agent_registry.json and add config keys to skills_config.default.json | `[ ]` |
| 06 | [06_ba_and_supervisor_routing_updates.md](./06_ba_and_supervisor_routing_updates.md) | Add frontend-coder to the BA archetype table and ticket-supervisor routing logic | `[ ]` |
