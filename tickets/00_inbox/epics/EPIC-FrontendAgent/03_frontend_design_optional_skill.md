---
title: "Author the frontend-design optional skill template"
status: todo
components:
  - build_pipeline
created: 2026-05-28
depends_on:
  - 01_frontend_coder_agent_template.md
priority: high
requires_diagram: false
requires_adr: false
files_touched:
  - leafcutter-ai/templates/skills/frontend-design/SKILL.md
agents:
  architect-review: needed
  python-coder: not_needed
  sql-coder: not_needed
  test-writer: not_needed
  test-runner: not_needed
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 03: Author the frontend-design optional skill template

## Actor / Goal

In order to prevent generic AI aesthetics in UI output, we need a `frontend-design` skill template that guides `frontend-coder` to make bold, distinctive design choices before writing any markup, CSS, or component code.

## Context

This is an optional skill — it is only installed when the user opts in during `/onboard` (or manually). The skill template lives in `leafcutter-ai/templates/skills/frontend-design/SKILL.md` and is deployed to `.claude/skills/frontend-design/SKILL.md` by `build.py`.

The `frontend-design` skill is consumed exclusively by `frontend-coder`. When `frontend-coder` detects the skill is installed, it loads the skill *before* writing any UI code and applies its design principles.

The skill should:
- Articulate design principles that counteract generic AI aesthetics: strong typographic hierarchy, intentional use of negative space, distinctive colour usage (not generic blue/grey), component-level personality
- Provide a design-review checklist that frontend-coder runs before signing off: "Does this look distinct from a default Tailwind/MUI output?", "Is there a clear visual hierarchy?", "Are interactive states (hover, focus, active) deliberate?"
- Include a project-context hook: if `PROJECT_CONTEXT.md` for frontend-coder exists and specifies a design system or brand colours, load those first and defer to them over the skill defaults
- Keep the skill platform-agnostic: the principles apply to React/Vue/plain HTML equally

Depends on ticket 01 because frontend-coder's optional-skill integration section determines when this skill is loaded.

## Acceptance Criteria

```gherkin
Given leafcutter-ai/templates/skills/frontend-design/SKILL.md is created
When build.py --target-dir . is run
Then .claude/skills/frontend-design/SKILL.md exists and passes the skill frontmatter guard

Given a frontend-coder agent loads the frontend-design skill
When it is about to write any markup, CSS, or component code
Then it applies the design principles from the skill before writing

Given a PROJECT_CONTEXT.md for frontend-coder specifies a design system
When the frontend-design skill is loaded
Then the skill defers to the project-specific design system over its own defaults

Given the skill is read by a developer
When they look for guidance on what "distinctive" means
Then the skill contains at least 5 concrete, non-vague design principles with examples
```

## Sign-offs

- [ ] architect-review
- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### documentation-expert

- [ ] Create `leafcutter-ai/templates/skills/frontend-design/SKILL.md` with: YAML frontmatter (name: frontend-design, allowed-tools: Read), a Purpose section explaining the anti-generic-AI-aesthetics goal, a Design Principles section with at least 5 concrete principles (e.g. "Use a custom font pairing, not the browser default"; "Choose a primary colour with a clear personality — avoid #3B82F6 as the default blue unless it is the project brand"), a Project Context Hook (load PROJECT_CONTEXT.md → design_system key if present, defer to brand values), a Pre-Write Checklist (questions frontend-coder asks before writing any UI output), and a Constraints section (platform-agnostic, no framework-specific imports).

## Risk & Safety

- Touches money? No.
- Touches data? No — skill is a markdown template.
- Reversibility? Fully reversible.
- Shared contract? The skill's design principles are referenced by frontend-coder. Principles can be updated independently without versioning concerns, as they are advisory (not contractual).
