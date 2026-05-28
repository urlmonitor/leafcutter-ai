---
title: "Reference: Agent Template Frontmatter"
status: todo
components:
  - build_pipeline
  - config_loader
created: 2026-05-28
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
requires_documentation:
  - reference
files_touched:
  - leafcutter-ai/docs/reference/agent-template-frontmatter.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: needed
  reference-author: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 06: Reference: Agent Template Frontmatter

## Actor / Goal

In order to give developers a single authoritative lookup table for all agent template frontmatter fields, we need a reference doc covering every runtime key and build directive so that no one needs to reverse-engineer existing templates to discover valid fields.

## Context

Agent template frontmatter has two categories of keys:
- **Runtime keys** — consumed by Claude Code at agent-invocation time (`name`, `description`, `model`, `tools`, `memory`).
- **Build directives** — consumed by `build.py` during compilation (`portable`, `signoff`, `domain`, `config_keys`, `adopter_notes`, `requires_verification`, `inject_registry`).

Currently, neither category is documented in a single place. The field list is spread across template headers, `build.py` source comments, and the `agent_registry.json` schema.

Source of truth for this reference:
- `leafcutter-ai/templates/agents/` — live template examples
- `leafcutter-ai/scripts/build.py` — build directive handling
- `leafcutter-ai/config/agent_registry.json` — registry schema

## Acceptance Criteria

```gherkin
Given the reference doc exists at leafcutter-ai/docs/reference/agent-template-frontmatter.md
When a developer reads it
Then they find a table with every frontmatter field, its type, required/optional status, default value, and a description of its effect

Given the doc covers both runtime keys and build directives
When it is read
Then runtime keys and build directives are in separate clearly-labelled sections

Given the doc lists valid values for enumerated fields
When it is read
Then fields like `model` and `tools` include their valid value sets and defaults

Given the doc is authored
When it passes the doc frontmatter guard
Then it has valid frontmatter including type: reference
```

## Sign-offs

- [ ] documentation-expert
- [ ] reference-author
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### documentation-expert / reference-author

- [ ] Read all existing agent templates in `leafcutter-ai/templates/agents/` to extract the full set of frontmatter keys actually in use.
- [ ] Read `leafcutter-ai/scripts/build.py` to identify all build directives it reads and what it does with them.
- [ ] Read `leafcutter-ai/config/agent_registry.json` for the registry schema (id, tier, visibility, is_ticket_phase, default_status, etc.) — note these are registry fields, not template frontmatter, but cross-link them.
- [ ] Write `leafcutter-ai/docs/reference/agent-template-frontmatter.md` with:
  - **Runtime keys table**: `name`, `description`, `model`, `tools`, `memory` — type, required/optional, default, effect.
  - **Build directives table**: `portable`, `signoff`, `domain`, `config_keys`, `adopter_notes`, `requires_verification`, `inject_registry` — type, required/optional, default, effect on `build.py` output.
  - **Cross-reference**: link to `agent_registry.json` schema fields (id, tier, visibility, is_ticket_phase, trigger_conditions, default_status, spawn_allowlist).
  - **Valid values** for each enumerated field (e.g., `model: sonnet | opus`, `tools: []` list of valid Claude Code tool names).
  - **Examples** — one minimal and one maximal frontmatter block.
- [ ] Ensure the doc has valid frontmatter (type: reference).

## Risk & Safety

- Touches money? No.
- Touches data? No — documentation only.
- Reversibility? Fully reversible.
