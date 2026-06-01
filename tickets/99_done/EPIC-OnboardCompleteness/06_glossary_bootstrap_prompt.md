---
title: "Prompt user to bootstrap glossary during onboard"
status: done
components:
  - onboard
created: 2026-05-19
depends_on: []
priority: low
requires_diagram: false
requires_adr: false
---

# 06: Prompt user to bootstrap glossary during onboard

## Actor / Goal

In order to have a populated glossary after onboarding, we need the onboard
agent to detect an empty glossary file and prompt the user to run
/glossary-bootstrap or flag it as a follow-up.

## Context

The glossary file exists after build but is empty. The check-glossary-coverage
pre-commit hook dispatches the glossary-triage agent on novel terms, but it
needs a baseline glossary to compare against. Without bootstrapping, every term
in the codebase looks "novel" to the triage hook.

## Acceptance Criteria

```gherkin
Given docs/glossary.md exists but is empty after build
When the onboard agent finishes
Then it asks the user "Run /glossary-bootstrap now to populate the glossary?"
And if the user says yes, it runs the bootstrap
And if the user says no, it adds glossary bootstrap to the post-onboard checklist
```

## Implementation Tasks

- [ ] Add glossary emptiness check to onboard agent template
- [ ] Prompt user with yes/no/later option
- [ ] If yes: invoke glossary-bootstrap
- [ ] If no: add to checklist output

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Glossary bootstrap is additive.
