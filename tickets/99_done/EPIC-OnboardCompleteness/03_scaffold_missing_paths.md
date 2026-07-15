---
title: "Scaffold missing config-referenced files during onboard"
status: done
components:
  - onboarding
  - build_pipeline
created: 2026-05-19
depends_on:
  - 02_referential_integrity.md
priority: medium
requires_diagram: false
requires_adr: false
---

# 03: Scaffold missing config-referenced files during onboard

## Actor / Goal

In order to have all downstream agents work out-of-the-box after onboarding,
we need the onboard pipeline to scaffold minimal-valid versions of every file
referenced in skills_config.json that nothing else creates.

## Context

After build.py runs, these files/directories referenced by skills_config.json
do not exist:

- `tests/README.md` (testing_context.readme_path) — test-planner agent needs this
- `.claude/precommit-autofix.json` (precommit_autofix_config_path) — autofix skill has no routing table
- `changelogs/` (changelog_folder) — changelog agent errors on first write
- `.claude/changelog_categories.md` (changelog_categories_path) — changelog categorization has no config

## Acceptance Criteria

```gherkin
Given a fresh project with skills_config.json referencing these paths
When the onboard agent completes
Then tests/README.md exists with a minimal testing conventions skeleton
And changelogs/ directory exists
And .claude/precommit-autofix.json exists with an empty routing table
And .claude/changelog_categories.md exists with default categories
```

## Implementation Tasks

- [ ] Create scaffold templates for each missing file in leafcutter/templates/
- [ ] Add a build phase or onboard step that writes scaffolds for missing paths
- [ ] Ensure scaffolds are minimal-valid (not empty, not placeholder-heavy)
- [ ] Tests

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? All scaffolds are new files; no overwrites.
