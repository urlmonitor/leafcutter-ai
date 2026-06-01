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
  documentation-expert: signed_off
  how-to-author: signed_off
  pr-reviewer: signed_off
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

- [x] documentation-expert — 2026-05-28 09:00
- [x] how-to-author — 2026-05-28 09:15
- [x] pr-reviewer — 2026-05-28 09:30
- [ ] commit
- [ ] pull-request

## Comments

### 2026-05-28 09:00 — documentation-expert (status: ok)
feedback-id: fb_2026-05-28_9de086ea
Researched SKILL.md frontmatter schema from existing skills (ticket-authoring, add-skill-to-package, signoff, building-epics) and skill_registry.json structure. Authored docs/how-to/creating-a-skill.md covering all 8 lifecycle steps: name choice, directory creation, frontmatter authoring (name/description/allowed-tools/internal), skill body structure, optional scripts/ subdirectory, registry registration, build.py deployment, and add-skill-to-package promotion. Included Common Mistakes table and See Also links. Doc has valid type: how_to frontmatter.

### 2026-05-28 09:15 — how-to-author (status: ok)
feedback-id: fb_2026-05-28_a47184cb
Reviewed guide against how-to structure requirements: fixed type field from how_to to how-to (per frontmatter_validators.py convention), promoted Prerequisites from bold text to ## Prerequisites heading, added ## Verification section with runnable four-step checklist, standardized ## Common Mistakes and ## See Also headings to H2. Guide passes YAML frontmatter validation (title, type: how-to, status: active, created, last_updated, components: [build_pipeline], related_docs). No README in docs/how-to/ to update.

### 2026-05-28 09:30 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-28_6cee1adc
Reviewed docs/how-to/creating-a-skill.md against all 3 acceptance criteria (Gherkin scenarios). All 15 content checks pass: directory creation, all frontmatter fields (name/description/allowed-tools/internal), scripts/ subdirectory, registry registration, build.py run, add-skill-to-package promotion, internal: true note, Common Mistakes table, valid type: how-to frontmatter, Prerequisites H2, Verification H2, See Also H2. Zero high-confidence findings. All four relative links resolve correctly. Diff size: 323 lines in 1 new file vs HEAD. Escalation: none (0 medium findings, threshold is >3).

## Implementation Tasks

### documentation-expert / how-to-author

- [x] Research the `SKILL.md` frontmatter schema by reading existing skills (`ticket-authoring`, `ticket-wiring`, `add-skill-to-package`). Extract all valid frontmatter fields (`name`, `description`, `allowed-tools`, `internal`).
- [x] Document the full skill creation lifecycle in `leafcutter-ai/docs/how-to/creating-a-skill.md`:
  1. Choose a skill name (kebab-case).
  2. Create `leafcutter-ai/templates/skills/<name>/` directory.
  3. Create `SKILL.md` with YAML frontmatter: `name`, `description`, `allowed-tools`, `internal` (true/false).
  4. Write the skill body (procedure, numbered steps, code blocks).
  5. Add an optional `scripts/` subdirectory for helper scripts the skill invokes.
  6. Register the skill in `leafcutter-ai/config/skill_registry.json` — add entry with `id`, `description`, `path`, `internal`.
  7. Run `python leafcutter-ai/scripts/build.py --target-dir .` and verify no errors.
  8. Verify `.claude/skills/<name>/SKILL.md` exists.
  9. For promotion to an adopter project: invoke the `add-skill-to-package` skill (post ticket 09 fix, this also updates the registry).
- [x] Include a note on the `internal: true` flag — skills marked internal are not copied to adopter projects.
- [x] Include a "Common Mistakes" table (missing `allowed-tools`, forgetting registry entry, wrong `internal` value).
- [x] Ensure the doc file has valid frontmatter (type: how_to).

## Risk & Safety

- Touches money? No.
- Touches data? No — documentation only.
- Reversibility? Fully reversible.
