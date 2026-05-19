---
title: "Add TODO/placeholder marker detection to build pipeline"
status: todo
components:
  - build_system
  - onboard
created: 2026-05-19
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
---

# 01: Add TODO/placeholder marker detection to build pipeline

## Actor / Goal

In order to prevent the onboard agent from treating placeholder files as complete,
we need build.py and the onboard agent to detect TODO/placeholder markers in generated
files so that users are alerted when critical content is still boilerplate.

## Context

`docs/vision.md` and `docs/roadmap.json` are written by build.py with 100% placeholder
content (e.g. `TODO: Replace with...`). The onboard agent sees the file exists and
moves on. The CLAUDE.md roadmap sentinel downstream still says "TODO: Replace with..."
after build completes.

## Acceptance Criteria

```gherkin
Given a file written by build.py contains "TODO:" or "PLACEHOLDER" markers
When the onboard agent runs
Then it flags each file with placeholder content and reports them to the user
```

## Implementation Tasks

- [ ] Define a set of placeholder marker patterns (TODO:, PLACEHOLDER, Replace with, etc.)
- [ ] Add a post-write scan in build.py that checks each output file for markers
- [ ] Return a list of files-with-placeholders from build.py to the caller
- [ ] Update onboard agent template to surface placeholder files to the user
- [ ] Tests for marker detection logic

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Additive check; no existing behaviour changes.
