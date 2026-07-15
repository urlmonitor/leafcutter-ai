---
title: "Check pre-commit availability and run install during onboard"
status: done
components:
  - onboarding
  - build_pipeline
created: 2026-05-19
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
---

# 05: Check pre-commit availability and run pre-commit install during onboard

## Actor / Goal

In order to have pre-commit hooks actually fire on commits after onboarding,
we need the onboard pipeline to verify pre-commit is installed, install it if
missing, and run `pre-commit install` to wire hooks into .git/hooks/.

## Context

build.py writes `.pre-commit-config.yaml` and "installs shims" but never runs
`pre-commit install`. The shims reference pre-commit but the tool may not be
installed in the environment. Result: hooks literally do not fire on any commit.

## Acceptance Criteria

```gherkin
Given a fresh project after build.py runs
When the onboard agent reaches the pre-commit phase
Then it checks if pre-commit is available in PATH
And if missing, it suggests pip install pre-commit (or uv tool install pre-commit)
And if available, it runs pre-commit install
And .git/hooks/pre-commit exists and is functional
```

## Implementation Tasks

- [ ] Add pre-commit availability check (which pre-commit / command -v pre-commit)
- [ ] If missing: prompt user with install command for their environment
- [ ] If present: run `pre-commit install` after build completes
- [ ] Verify .git/hooks/pre-commit exists and is executable
- [ ] Add to post-onboard checklist if skipped

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? pre-commit install is idempotent; pre-commit uninstall reverses it.
