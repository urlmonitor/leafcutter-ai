---
title: "Add default_artifact_checklist to how-to-author"
status: todo
components:
  - build_pipeline
created: 2026-05-28
depends_on:
  - 01_signoff_skill_manifest_section.md
priority: high
requires_diagram: false
requires_adr: false
agents:
  documentation-expert: signed_off
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
---

# 02_17: Add default_artifact_checklist to how-to-author

## Goal
Add `default_artifact_checklist` YAML frontmatter to `templates/agents/how-to-author.md` so the agent always confirms these items in its `completion_manifest:` block on sign-off.

## Context
The how-to-author agent (priority 10, role: documentation) writes task-oriented how-to guides. Its checklist should confirm the guide was written, placed in the correct location, and the steps are validated.

Source of truth: `config/agent_registry.json` entry with `"id": "how-to-author"`.

## Checklist Items
```yaml
default_artifact_checklist:
  - guide_written
  - location_correct
  - steps_validated
```

## Acceptance Criteria
```gherkin
Given templates/agents/how-to-author.md is read
When the frontmatter is parsed
Then a default_artifact_checklist key is present as a YAML list
And it contains exactly: guide_written, location_correct, steps_validated
```

## Sign-offs

- [x] documentation-expert — 2026-05-29 12:00
- [x] pr-reviewer — 2026-05-29 12:05
- [ ] commit
- [ ] pull-request

## Implementation Tasks

### documentation-expert
- [x] Edit `templates/agents/how-to-author.md` frontmatter: add `default_artifact_checklist: [guide_written, location_correct, steps_validated]`
- [x] Add instruction paragraph in body referencing signoff §2b completion_manifest requirement

## Comments

### 2026-05-29 12:00 — documentation-expert (status: ok)
feedback-id: fb_2026-05-29_c347002e
completion_manifest:
  guide_written: true
  location_correct: true
  steps_validated: true
Added `default_artifact_checklist` YAML block to `templates/agents/how-to-author.md` frontmatter with items `guide_written`, `location_correct`, `steps_validated`. Added step 6 in the Execution Loop instructing the agent to populate `completion_manifest:` on sign-off referencing signoff §2b.

### 2026-05-29 12:05 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-29_4a92f00d
completion_manifest:
  acceptance_criteria_met: true
  change_scope_correct: true
  no_regressions_found: true
Reviewed the diff: `default_artifact_checklist` correctly added to frontmatter with the three specified items, and step 6 in the Execution Loop correctly instructs the agent to use these items in `completion_manifest:` on sign-off referencing signoff §2b. All acceptance criteria satisfied. Approved.
