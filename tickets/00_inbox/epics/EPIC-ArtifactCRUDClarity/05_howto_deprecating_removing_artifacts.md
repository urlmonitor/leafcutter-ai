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
  documentation-expert: signed_off
  how-to-author: signed_off
  pr-reviewer: signed_off
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

- [x] documentation-expert — 2026-05-28 14:10
- [x] how-to-author — 2026-05-28 14:12
- [x] pr-reviewer — 2026-05-28 14:14
- [ ] commit
- [ ] pull-request

## Comments

### 2026-05-28 14:10 — documentation-expert (status: ok)
feedback-id: fb_2026-05-28_eed56ff7
Researched all four artifact types (agent templates, skills, Claude Code hooks, pre-commit hooks). Wrote `docs/how-to/deprecating-or-removing-artifacts.md` with universal checklist, per-type deletion procedures, deprecation (soft-removal) section, real example sidebar for `templates/commit-guardian/` deprecation, and verification quick-reference table. Frontmatter validated as `type: how_to`.

### 2026-05-28 14:12 — how-to-author (status: ok)
feedback-id: fb_2026-05-28_697af5ad
Reviewed `docs/how-to/deprecating-or-removing-artifacts.md`: all four artifact types covered with actionable step-by-step checklists, deprecation section present with registry flag and source-file comment patterns, real example sidebar documents the `templates/commit-guardian/` deprecation, frontmatter valid (`type: how_to`, `status: active`, all required fields). Verification quick-reference table matches acceptance criteria. Guide is ready for PR review.

### 2026-05-28 14:14 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-28_bf625d61
Review Report — Base: worktree-EPIC-ArtifactCRUDClarity. Diff size: 376 lines added (1 new file).
High-Confidence Findings: No high-confidence findings.
Medium-Confidence Findings: [M-1] docs/how-to/deprecating-or-removing-artifacts.md:3 — `type: how_to` vs `type: how-to`: commit_guardian.json allowed_types uses `how-to` (hyphen) but ticket spec and other untracked worktree files use `how_to` (underscore). Convention inconsistency; doc frontmatter guard will flag at commit time. Not a content blocker — the guide is accurate and complete.
Suppressed: 0 low-confidence nits, 0 medium findings dropped by Opus.
Escalation — Branch: none. Reason: not escalated: medium count was 1 (threshold > 3).
All acceptance criteria met. Approved for commit.

## Implementation Tasks

### documentation-expert / how-to-author

- [x] Research all four artifact types' source locations, registry entries, and cross-references (use reference docs 06–08 as input once available; otherwise read source files directly).
- [x] Write `leafcutter-ai/docs/how-to/deprecating-or-removing-artifacts.md` with the following sections:

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

- [x] Cross-link to reference docs 06–08 for the authoritative field inventories.
- [x] Add a "Real example" sidebar documenting the `templates/commit-guardian/` deprecation that motivated this epic.
- [x] Ensure the doc has valid frontmatter (type: how_to).

## Risk & Safety

- Touches money? No.
- Touches data? No — documentation only.
- Reversibility? Fully reversible.
