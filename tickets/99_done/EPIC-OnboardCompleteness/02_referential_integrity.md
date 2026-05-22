---
title: "Post-build referential integrity check for skills_config.json"
status: done
components:
  - build_system
created: 2026-05-19
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
---

# 02: Post-build referential integrity check for skills_config.json

## Actor / Goal

In order to catch missing files before downstream agents fail at runtime,
we need a post-build validation step that checks every path referenced in
skills_config.json actually exists on disk.

## Context

skills_config.json references paths like `testing_context.readme_path`,
`precommit_autofix_config_path`, `changelog_folder`, and `changelog_categories_path`.
None of these are created by build.py or the onboard agent. Downstream agents
(test-planner, precommit-autofix, changelog) fail silently or error when they
try to load these missing files.

## Acceptance Criteria

```gherkin
Given build.py has completed
When the referential integrity check runs
Then every file/directory path in skills_config.json is verified to exist
And missing paths are reported with their config key and expected location
```

## Implementation Tasks

- [ ] Parse skills_config.json and extract all path-valued fields
- [ ] Check each path exists relative to the target root
- [ ] Report missing paths with actionable messages (config key + expected path)
- [ ] Wire check into build.py as a post-build phase (warning, not blocking)
- [ ] Tests

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Additive validation step; does not change build output.
