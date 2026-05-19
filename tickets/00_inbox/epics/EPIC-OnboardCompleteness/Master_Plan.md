---
title: "EPIC: Onboard Agent Completeness"
type: epic
status: todo
components:
  - onboard
  - build_system
created: 2026-05-19
depends_on: []
requires_diagram: false
requires_adr: false
---

# EPIC: Onboard Agent Completeness

## Actor / Goal

In order to have a fully functional leafcutter installation after running the onboard agent,
we need to fix the onboard pipeline so that it detects placeholder content, validates
referential integrity, scaffolds all referenced paths, and produces a post-onboard checklist
— so that no downstream agent silently fails because a config-referenced file is missing.

## Context

The onboard agent currently discovers `skills_config.json` and runs `build.py`, then stops.
It treats "file exists" as "file is complete" and never checks whether paths referenced in
`skills_config.json` actually exist. This leaves 11+ gaps that surface as runtime failures
in downstream agents (changelog, test-planner, precommit-autofix, glossary).

### Root Causes

1. **"File exists = done" logic** — `build.py` and the onboard agent treat file presence as
   completion, with no placeholder/TODO detection.
2. **No referential integrity check** — `skills_config.json` references paths that nothing
   creates; no validation that referenced files exist after build.
3. **Onboard scope too narrow** — it only owns config discovery + build; vision, roadmap,
   pre-commit installation, and supporting configs are orphaned.
4. **No post-onboard checklist** — there is no "here's what you still need to do manually"
   output at the end.

## Sub-Tickets

| # | File | Description | Status |
|---|------|-------------|--------|
| 01 | [01_placeholder_detection.md](./01_placeholder_detection.md) | Add TODO/placeholder marker detection to build.py and onboard agent | `[ ]` |
| 02 | [02_referential_integrity.md](./02_referential_integrity.md) | Post-build validation that every path in skills_config.json exists | `[ ]` |
| 03 | [03_scaffold_missing_paths.md](./03_scaffold_missing_paths.md) | Scaffold missing files referenced by skills_config.json (tests/README.md, changelogs/, .claude/precommit-autofix.json, .claude/changelog_categories.md) | `[ ]` |
| 04 | [04_vision_roadmap_interactive.md](./04_vision_roadmap_interactive.md) | Onboard detects placeholder vision.md and roadmap.json, walks user through filling interactively | `[ ]` |
| 05 | [05_precommit_install.md](./05_precommit_install.md) | Check pre-commit tool availability and run pre-commit install after build | `[ ]` |
| 06 | [06_glossary_bootstrap_prompt.md](./06_glossary_bootstrap_prompt.md) | Prompt user to run /glossary-bootstrap when glossary file is empty | `[ ]` |
| 07 | [07_post_onboard_checklist.md](./07_post_onboard_checklist.md) | Generate and display a post-onboard checklist of remaining manual steps | `[ ]` |

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? All changes are additive to the onboard pipeline; existing onboard behaviour is preserved for the happy path.
