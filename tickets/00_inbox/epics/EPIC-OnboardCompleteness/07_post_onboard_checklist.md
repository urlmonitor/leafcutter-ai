---
title: "Generate post-onboard checklist of remaining manual steps"
status: todo
components:
  - onboard
created: 2026-05-19
depends_on:
  - 01_placeholder_detection.md
  - 02_referential_integrity.md
priority: medium
requires_diagram: false
requires_adr: false
---

# 07: Generate post-onboard checklist of remaining manual steps

## Actor / Goal

In order to know what still needs attention after onboarding completes,
we need the onboard agent to output a structured checklist of everything
that was skipped, deferred, or still needs manual input.

## Context

Currently onboard ends silently after build.py runs — the user has no idea
that vision.md is placeholder, glossary is empty, pre-commit hooks aren't
wired, and several config-referenced files don't exist. A checklist at the
end would make these gaps visible and actionable.

## Acceptance Criteria

```gherkin
Given the onboard agent has completed all its phases
When it reaches the final step
Then it outputs a markdown checklist grouped by category
And each item includes: what's missing, why it matters, and the command to fix it
And items already completed during onboard are marked done
```

## Implementation Tasks

- [ ] Collect results from placeholder detection (ticket 01)
- [ ] Collect results from referential integrity check (ticket 02)
- [ ] Collect skipped interactive steps (vision, roadmap, glossary)
- [ ] Collect pre-commit install status
- [ ] Format as a markdown checklist with categories and fix commands
- [ ] Print to user at end of onboard run

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Pure output; no side effects.
