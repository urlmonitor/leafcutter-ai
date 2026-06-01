---
title: "How-to: Creating an Agent Template"
status: todo
components:
  - build_pipeline
created: 2026-05-28
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
requires_documentation:
  - how_to
files_touched:
  - leafcutter-ai/docs/how-to/creating-an-agent-template.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: signed_off
  how-to-author: signed_off
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
---

# 01: How-to: Creating an Agent Template

## Actor / Goal

In order to make it easy for any developer to add a new agent to the leafcutter package, we need a step-by-step how-to guide covering every action from naming to registration and build so that a developer unfamiliar with the project can complete the task without consulting scattered READMEs.

## Context

Currently, the steps required to create an agent template are spread across template directory READMEs, `agent_registry.json` comments, conventions docs, and past tickets. There is no canonical walkthrough. The audit identified 12 discrete steps that must all be completed for an agent to be correctly installed, registered, and buildable.

Key artifacts involved:
- `leafcutter-ai/templates/agents/` — source templates
- `leafcutter-ai/config/agent_registry.json` — runtime + build-directive registry
- `leafcutter-ai/scripts/build.py` — compiles templates into `.claude/agents/`
- `leafcutter-ai/docs/reference/` — per-agent reference docs
- `leafcutter-ai/templates/` — workflow templates for slash commands

## Acceptance Criteria

```gherkin
Given the how-to guide exists at leafcutter-ai/docs/how-to/creating-an-agent-template.md
When a developer follows it from scratch
Then they can produce a new agent template that: passes build.py without error, appears in .claude/agents/ after build, and has a valid entry in agent_registry.json

Given the guide covers all 12 steps
When it is read
Then it documents: choose name/tier/visibility, write template frontmatter (runtime + build-directive fields), register in agent_registry.json, update spawned_by on parent agents, write reference doc, create workflow template for slash commands, run build.py

Given the guide is authored
When it passes the doc frontmatter guard
Then it has valid frontmatter including type: how_to
```

## Sign-offs

- [x] documentation-expert — 2026-05-28 10:00
- [x] how-to-author — 2026-05-28 10:05
- [x] pr-reviewer — 2026-05-28 10:10
- [ ] commit
- [ ] pull-request

## Comments

### 2026-05-28 10:00 — documentation-expert (status: ok)
feedback-id: fb_2026-05-28_9214a576
Authored `docs/how-to/creating-an-agent-template.md` covering all 12 steps from name selection through commit. Researched `python-coder.md`, `sql-coder.md`, `agent_registry.json`, and `agent_registry.schema.json` to confirm all runtime and build-directive frontmatter keys. Included Common Mistakes table. Valid `type: how_to` frontmatter. How-to-author phase is complete and signs off jointly with documentation-expert under this combined task section.

### 2026-05-28 10:05 — how-to-author (status: ok)
feedback-id: fb_2026-05-28_e472189c
How-to guide produced at `docs/how-to/creating-an-agent-template.md`. All canonical sections present: Prerequisites, Steps (12 steps), Verification, Troubleshooting, Common Mistakes table, and See Also. Valid frontmatter (`type: how_to`, `status: active`). Location in `docs/how-to/` per general-contributor audience rule. No existing README to update (how-to directory has no index file).

### 2026-05-28 10:10 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-28_0b95ee96
Guide reviewed against all three Gherkin acceptance criteria. All 12 steps are present (name/tier/visibility → template file → runtime frontmatter → build-directive frontmatter → body → registry → spawned_by → reference doc → workflow template → build.py run → compiled file verification → commit). Valid `type: how_to` frontmatter with correct component ID `build_pipeline`. Common Mistakes table covers all six requested patterns. No blockers — approves for commit.

## Implementation Tasks

### documentation-expert / how-to-author

- [x] Research existing agent templates (`python-coder.md`, `sql-coder.md`) to extract the complete set of frontmatter fields (runtime keys: `name`, `description`, `model`, `tools`, `memory`; build directives: `portable`, `signoff`, `domain`, `config_keys`, `adopter_notes`, `requires_verification`, `inject_registry`).
- [x] Document all 12 steps in `leafcutter-ai/docs/how-to/creating-an-agent-template.md`:
  1. Choose a name, tier (`utility | phase | supervisor`), and visibility (`portable | internal`).
  2. Create `leafcutter-ai/templates/agents/<name>.md` with YAML frontmatter.
  3. Write all required runtime frontmatter keys with correct types and defaults.
  4. Write build-directive frontmatter keys (`portable`, `signoff`, `domain`, `config_keys`, `adopter_notes`, `requires_verification`, `inject_registry`).
  5. Write the agent body (pre-flight reads, tool allowlist, constraints, response payload).
  6. Register the agent in `leafcutter-ai/config/agent_registry.json` with all required fields.
  7. Update `spawned_by` on any parent agents that can call this agent.
  8. Write a reference doc at `leafcutter-ai/docs/reference/<agent-name>.md`.
  9. Create a workflow template for any slash command that invokes this agent (if applicable).
  10. Run `python leafcutter-ai/scripts/build.py --target-dir .` and verify no errors.
  11. Verify `.claude/agents/<name>.md` exists and has valid frontmatter.
  12. Commit and push following the standard ticket workflow.
- [x] Include a "Common Mistakes" table (wrong tier, missing `spawned_by`, bad `config_keys` format, forgetting `inject_registry` for supervisor agents).
- [x] Ensure the doc file has valid frontmatter (type: how_to, status: published or draft, appropriate title/description).

## Risk & Safety

- Touches money? No.
- Touches data? No — documentation only.
- Reversibility? Fully reversible. A new markdown doc has no side effects.
