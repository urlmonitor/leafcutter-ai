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
  documentation-expert: needed
  how-to-author: needed
  pr-reviewer: needed
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

- [ ] documentation-expert
- [ ] how-to-author
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### documentation-expert / how-to-author

- [ ] Research existing agent templates (`python-coder.md`, `sql-coder.md`) to extract the complete set of frontmatter fields (runtime keys: `name`, `description`, `model`, `tools`, `memory`; build directives: `portable`, `signoff`, `domain`, `config_keys`, `adopter_notes`, `requires_verification`, `inject_registry`).
- [ ] Document all 12 steps in `leafcutter-ai/docs/how-to/creating-an-agent-template.md`:
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
- [ ] Include a "Common Mistakes" table (wrong tier, missing `spawned_by`, bad `config_keys` format, forgetting `inject_registry` for supervisor agents).
- [ ] Ensure the doc file has valid frontmatter (type: how_to, status: published or draft, appropriate title/description).

## Risk & Safety

- Touches money? No.
- Touches data? No — documentation only.
- Reversibility? Fully reversible. A new markdown doc has no side effects.
