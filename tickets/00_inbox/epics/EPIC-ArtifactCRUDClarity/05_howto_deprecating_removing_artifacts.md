---
title: "How-to: Deprecating or Removing Artifacts"
status: todo
components:
  - build_pipeline
  - config_loader
created: 2026-05-28
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
requires_documentation:
  - how_to
files_touched:
  - leafcutter-ai/docs/how-to/deprecating-or-removing-artifacts.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: needed
  how-to-author: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 05: How-to: Deprecating or Removing Artifacts

## Actor / Goal

In order to prevent the registry drift and stale build output problems identified in the audit, we need a universal deprecation/deletion guide covering all four artifact types so that developers know exactly what files to remove, which registries to update, and how to verify nothing is left orphaned.

## Context

Currently there is no documented procedure for removing any artifact type. This has led to:
- `templates/commit-guardian/` being deprecated but still referenced by `create-hook` (fixed in ticket 10).
- 4 skills on disk with no registry entry (fixed in ticket 11).
- Stale compiled artifacts persisting in `.claude/` after source templates are deleted (fixed in ticket 12 via `--clean` flag).

This guide should be the single reference for all four types. It can note that reference docs 06–08 provide the full field inventories for each type. It should also document the `build.py --clean` workflow as the verification step for confirming cleanup.

## Acceptance Criteria

```gherkin
Given the how-to guide exists at leafcutter-ai/docs/how-to/deprecating-or-removing-artifacts.md
When a developer follows the "remove agent template" section
Then they know: which source file to delete, which registry entries to remove, which cross-references (spawned_by, docs) to clean, and how to verify with build.py --clean

Given the guide covers all four artifact types
When it is read
Then it has a section for each: agent templates, skills, Claude Code hooks, and pre-commit hooks

Given the guide covers deprecation (soft removal)
When a developer follows it
Then they can mark an artifact deprecated without deleting it, including the in-source deprecation marker and registry flag

Given the guide is authored
When it passes the doc frontmatter guard
Then it has valid frontmatter including type: how_to
```

## Sign-offs

- [ ] documentation-expert
- [ ] how-to-author
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### documentation-expert / how-to-author

- [ ] Research all four artifact types' source locations, registry entries, and cross-references (use reference docs 06–08 as input once available; otherwise read source files directly).
- [ ] Write `leafcutter-ai/docs/how-to/deprecating-or-removing-artifacts.md` with the following sections:

  **Universal checklist (applies to all types):**
  - Back up or tag before deleting.
  - Search for all cross-references before removing source files.
  - Run `build.py --clean` after deletion to remove compiled artifacts.
  - Verify with `git status` that no stale files remain.

  **Agent Templates:**
  - Delete `leafcutter-ai/templates/agents/<name>.md`.
  - Remove entry from `leafcutter-ai/config/agent_registry.json`.
  - Remove `spawned_by` references in all agents that list this agent.
  - Remove reference doc at `leafcutter-ai/docs/reference/<agent-name>.md`.
  - Remove slash-command workflow template if one exists.

  **Skills:**
  - Delete `leafcutter-ai/templates/skills/<name>/` directory.
  - Remove entry from `leafcutter-ai/config/skill_registry.json`.
  - Search skill bodies for `# <name>` or `add-skill-to-package` references and clean.

  **Claude Code Hooks:**
  - Delete `leafcutter-ai/templates/hooks/<name>.py`.
  - Remove the registration entry from `leafcutter-ai/templates/settings.json`.
  - Run `build.py` to remove from `.claude/hooks/` and `.claude/settings.json`.

  **Pre-Commit Hooks:**
  - Delete `leafcutter-ai/templates/scripts/commit_guardian/<name>.py`.
  - Remove entry from `commit_guardian.json`.
  - Remove from hooks manifest.
  - Run `build.py --clean`.

  **Deprecation (soft removal, all types):**
  - Add `_deprecated: true` to the registry entry.
  - Add a deprecation comment to the source file header.
  - Update cross-references to point to the replacement artifact.
  - Do NOT delete the source file until all consumers have migrated.

- [ ] Cross-link to reference docs 06–08 for the authoritative field inventories.
- [ ] Add a "Real example" sidebar documenting the `templates/commit-guardian/` deprecation that motivated this epic.
- [ ] Ensure the doc has valid frontmatter (type: how_to).

## Risk & Safety

- Touches money? No.
- Touches data? No — documentation only.
- Reversibility? Fully reversible.
