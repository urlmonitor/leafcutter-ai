---
title: "EPIC: Artifact CRUD Clarity"
type: epic
status: todo
components:
  - build_pipeline
  - config_loader
created: 2026-05-28
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
---

# EPIC: Artifact CRUD Clarity

Make creating, modifying, and deleting the four main leafcutter artifact types
(agent templates, skills, Claude Code hooks, pre-commit hooks) crystal clear
through comprehensive how-to guides, reference docs, and targeted code fixes
that eliminate registry drift, path confusion, and stale build outputs.

## Background

An audit of the four artifact types surfaced seven structural problems:

1. No how-to guides for any CRUD operation — steps are scattered across READMEs, skill bodies, past tickets, and conventions docs.
2. Deletion/deprecation is undocumented everywhere.
3. `build.py` copies/compiles forward but never removes orphaned artifacts.
4. Dual-location confusion for pre-commit hooks — `templates/commit-guardian/` (deprecated) vs `templates/scripts/commit_guardian/` (canonical). The `create-hook` skill references the deprecated path.
5. Claude Code hooks vs pre-commit hooks naming collision — both called "hooks", overlapping directories.
6. Skill registry drifts from disk — 4 skills on disk not in `skill_registry.json`. `add-skill-to-package` doesn't update it.
7. No `create-claude-hook` automation — pre-commit hooks have `create-hook`, Claude Code hooks are manual.

## Success Criteria

- A developer unfamiliar with the project can create, modify, and delete any of the 4 artifact types by following the how-to guides alone.
- All registry/disk mismatches are caught by automated validation.
- `build.py --clean` removes orphaned compiled artifacts.

## Sub-Tickets

| # | File | Description | Status |
|---|------|-------------|--------|
| 01 | [01_howto_creating_agent_template.md](./01_howto_creating_agent_template.md) | How-to: Creating an Agent Template | `[ ]` |
| 02 | [02_howto_creating_a_skill.md](./02_howto_creating_a_skill.md) | How-to: Creating a Skill | `[ ]` |
| 03 | [03_howto_managing_pre_commit_hooks.md](./03_howto_managing_pre_commit_hooks.md) | How-to: Managing Pre-Commit Hooks | `[ ]` |
| 04 | [04_howto_creating_claude_code_hook.md](./04_howto_creating_claude_code_hook.md) | How-to: Creating a Claude Code Hook | `[ ]` |
| 05 | [05_howto_deprecating_removing_artifacts.md](./05_howto_deprecating_removing_artifacts.md) | How-to: Deprecating or Removing Artifacts | `[ ]` |
| 06 | [06_ref_agent_template_frontmatter.md](./06_ref_agent_template_frontmatter.md) | Reference: Agent Template Frontmatter | `[ ]` |
| 07 | [07_ref_skill_frontmatter.md](./07_ref_skill_frontmatter.md) | Reference: Skill Frontmatter | `[ ]` |
| 08 | [08_ref_claude_code_hooks.md](./08_ref_claude_code_hooks.md) | Reference: Claude Code Hooks | `[ ]` |
| 09 | [09_fix_add_skill_registry_update.md](./09_fix_add_skill_registry_update.md) | Fix: add-skill-to-package registry update | `[ ]` |
| 10 | [10_fix_create_hook_canonical_path.md](./10_fix_create_hook_canonical_path.md) | Fix: create-hook canonical path | `[ ]` |
| 11 | [11_fix_skill_registry_validation.md](./11_fix_skill_registry_validation.md) | Fix: Bidirectional skill registry validation | `[ ]` |
| 12 | [12_fix_build_clean_mode.md](./12_fix_build_clean_mode.md) | Fix: build.py --clean mode | `[ ]` |

## Phases

### Phase 1 — Documentation (tickets 01–08)
All doc tickets are independent of each other and can be parallelised. Ticket 05 (deprecation guide) benefits from 06–08 being done first but is not strictly blocked.

### Phase 2 — Code Fixes (tickets 09–12)
All code fix tickets are independent of each other and of Phase 1.
