---
title: "Reference: Skill Frontmatter"
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
  - leafcutter-ai/docs/reference/skill-frontmatter.md
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

# 07: Reference: Skill Frontmatter

## Actor / Goal

In order to give developers a single authoritative lookup for `SKILL.md` frontmatter, we need a reference doc covering all fields, valid values, and format conventions so that new skills are authored correctly the first time.

## Context

Skills use a simple frontmatter schema in `SKILL.md`: `name`, `description`, `allowed-tools`, `internal`. These are not currently documented in a reference doc. Developers learn the schema by reading existing skills, leading to inconsistencies (e.g., some skills omit `internal`, some use `allowed-tools: []` vs listing tools one per line).

Source of truth:
- `leafcutter-ai/templates/skills/` — existing skill examples
- `leafcutter-ai/config/skill_registry.json` — registry schema (parallel to frontmatter)

## Acceptance Criteria

```gherkin
Given the reference doc exists at leafcutter-ai/docs/reference/skill-frontmatter.md
When a developer reads it
Then they find a table with every SKILL.md frontmatter field, its type, required/optional status, valid values, and a description

Given the doc covers `allowed-tools`
When it is read
Then it lists all valid tool names a skill can declare and explains the restriction contract

Given the doc covers the `internal` flag
When it is read
Then it explains when to set true vs false and the effect on build.py and add-skill-to-package

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

- [ ] Read all existing skills in `leafcutter-ai/templates/skills/` to extract the complete set of frontmatter keys and their observed values.
- [ ] Read `leafcutter-ai/config/skill_registry.json` to extract the registry-side schema and how it maps to frontmatter.
- [ ] Write `leafcutter-ai/docs/reference/skill-frontmatter.md` with:
  - **Frontmatter fields table**: `name`, `description`, `allowed-tools`, `internal` — type, required/optional, default, valid values, effect.
  - **`allowed-tools` details**: list all valid tool name strings (`Bash`, `Read`, `Edit`, `Write`, `Glob`, `Grep`, `Agent`, `mcp`, plus `Bash(<pattern>)` constrained forms). Explain that declaring a tool grants the skill user permission to use it within that skill's context.
  - **`internal` flag**: `true` = skill is not copied to adopter projects by `build.py`; `false` (default) = skill is public and deployed.
  - **Format conventions**: YAML block scalar vs flow style for `allowed-tools`, multi-line `description` quoting.
  - **skill_registry.json schema**: `id`, `description`, `path`, `internal` fields and their relationship to frontmatter values.
  - **Examples** — one minimal skill frontmatter and one with all fields.
- [ ] Ensure the doc has valid frontmatter (type: reference).

## Risk & Safety

- Touches money? No.
- Touches data? No — documentation only.
- Reversibility? Fully reversible.
