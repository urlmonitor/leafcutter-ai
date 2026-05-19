---
title: "Interactive vision.md and roadmap.json completion during onboard"
status: todo
components:
  - onboard
created: 2026-05-19
depends_on:
  - 01_placeholder_detection.md
priority: medium
requires_diagram: false
requires_adr: false
---

# 04: Interactive vision.md and roadmap.json completion during onboard

## Actor / Goal

In order to have meaningful project vision and roadmap content after onboarding,
we need the onboard agent to detect that vision.md and roadmap.json are pure
placeholders and walk the user through filling them interactively.

## Context

build.py writes vision.md and roadmap.json with TODO placeholders. The onboard
agent sees they exist and moves on. The CLAUDE.md roadmap sentinel downstream
still says "TODO: Replace with..." — a visible symptom of this gap. The vision
and roadmap files are meant to be project-specific content that only the user
can provide.

## Acceptance Criteria

```gherkin
Given docs/vision.md contains placeholder markers after build
When the onboard agent reaches the vision/roadmap phase
Then it prompts the user with guided questions about their project vision
And it writes user-provided content into vision.md
And it prompts for roadmap phases and milestones
And it writes user-provided content into roadmap.json
And the CLAUDE.md roadmap sentinel reflects the real roadmap
```

## Implementation Tasks

- [ ] Add vision/roadmap detection to onboard agent template
- [ ] Design interactive question flow for vision (project goal, audience, key outcomes)
- [ ] Design interactive question flow for roadmap (phases, milestones, timelines)
- [ ] Update CLAUDE.md roadmap sentinel after roadmap.json is populated
- [ ] Allow user to skip with a "fill later" option

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? User can re-run or edit files manually.
