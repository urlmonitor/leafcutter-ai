---
title: "How-to: Creating a Skill"
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
  - leafcutter-ai/docs/how-to/creating-a-skill.md
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

# 02: How-to: Creating a Skill

## Actor / Goal

In order to make it easy for any developer to add a new skill to the leafcutter package, we need an end-to-end how-to guide so that a developer can create, register, and promote a skill without consulting scattered docs.

## Context

Skills live in `leafcutter-ai/templates/skills/<skill-name>/SKILL.md` with an optional `scripts/` subdirectory. There is currently no canonical walkthrough for creating one. The audit found that `add-skill-to-package` exists for promotion but does not update `skill_registry.json` (fixed in ticket 09), and there are 4 skills on disk not in the registry (fixed in ticket 11).

Key artifacts:
- `leafcutter-ai/templates/skills/` — skill source templates
- `leafcutter-ai/config/skill_registry.json` — registry of all skills
- `add-skill-to-package` skill — promotion workflow
- `leafcutter-ai/scripts/build.py` — deploys skills to `.claude/skills/`

## Acceptance Criteria

```gherkin
Given the how-to guide exists at leafcutter-ai/docs/how-to/creating-a-skill.md
When a developer follows it from scratch
Then they can produce a new skill that: has correct SKILL.md frontmatter, appears in skill_registry.json, and is deployed to .claude/skills/ after build.py

Given the guide covers the full lifecycle
When it is read
Then it documents: create directory + SKILL.md, all frontmatter fields, optional scripts/ subdirectory, register in skill_registry.json, run build.py, and promotion via add-skill-to-package

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

- [ ] Research the `SKILL.md` frontmatter schema by reading existing skills (`ticket-authoring`, `ticket-wiring`, `add-skill-to-package`). Extract all valid frontmatter fields (`name`, `description`, `allowed-tools`, `internal`).
- [ ] Document the full skill creation lifecycle in `leafcutter-ai/docs/how-to/creating-a-skill.md`:
  1. Choose a skill name (kebab-case).
  2. Create `leafcutter-ai/templates/skills/<name>/` directory.
  3. Create `SKILL.md` with YAML frontmatter: `name`, `description`, `allowed-tools`, `internal` (true/false).
  4. Write the skill body (procedure, numbered steps, code blocks).
  5. Add an optional `scripts/` subdirectory for helper scripts the skill invokes.
  6. Register the skill in `leafcutter-ai/config/skill_registry.json` — add entry with `id`, `description`, `path`, `internal`.
  7. Run `python leafcutter-ai/scripts/build.py --target-dir .` and verify no errors.
  8. Verify `.claude/skills/<name>/SKILL.md` exists.
  9. For promotion to an adopter project: invoke the `add-skill-to-package` skill (post ticket 09 fix, this also updates the registry).
- [ ] Include a note on the `internal: true` flag — skills marked internal are not copied to adopter projects.
- [ ] Include a "Common Mistakes" table (missing `allowed-tools`, forgetting registry entry, wrong `internal` value).
- [ ] Ensure the doc file has valid frontmatter (type: how_to).

## Risk & Safety

- Touches money? No.
- Touches data? No — documentation only.
- Reversibility? Fully reversible.
