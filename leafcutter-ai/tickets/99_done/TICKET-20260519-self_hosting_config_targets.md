---
title: "Implement self-hosting: separate config targets for leafcutter development"
status: done
components:
  - build_system
  - onboard
created: 2026-05-19
completed: 2026-05-19
depends_on: []
priority: high
requires_diagram: false
requires_adr: true
---

# Implement self-hosting: separate config targets for leafcutter development

## Resolution

Implemented via config-driven path resolution (ADR-001) rather than the originally proposed `--self` flag. All project content now lives under `leafcutter-ai/` and `build.py` reads scaffold paths from `skills_config.json`.

Key commits:
- `ec63f91` — feat: make build.py fully config-driven and require onboarding
- `02aa8db` — fix(tests): update stale script paths

ADR: `leafcutter-ai/docs/architecture/adrs/ADR-001-self-hosting-boundary.md`
