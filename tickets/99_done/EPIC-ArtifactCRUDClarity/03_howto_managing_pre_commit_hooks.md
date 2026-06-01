---
title: "How-to: Managing Pre-Commit Hooks"
status: todo
components:
  - build_pipeline
created: 2026-05-28
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
requires_documentation:
  - how_to
files_touched:
  - leafcutter-ai/docs/how-to/managing-pre-commit-hooks.md
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

# 03: How-to: Managing Pre-Commit Hooks

## Actor / Goal

In order to make pre-commit hook lifecycle management understandable, we need a guide covering create, modify, disable, and delete operations via `commit_guardian.json` and the hooks manifest so that developers stop editing the wrong location or leaving stale hook registrations.

## Context

Pre-commit hooks in leafcutter are managed through two mechanisms:
- `leafcutter-ai/config/commit_guardian.json` — the runtime configuration that enables/disables hooks and sets their parameters
- `leafcutter-ai/templates/scripts/commit_guardian/` — the **canonical** location for hook scripts (not the deprecated `templates/commit-guardian/` path)
- `leafcutter-ai/config/hooks_manifest.json` (or equivalent) — the list of hooks deployed by build.py

The audit found that the `create-hook` skill references the deprecated `templates/commit-guardian/` path (fixed in ticket 10). This how-to should document the canonical path only, explain the confusion, and provide clear CRUD steps.

**Naming note**: "pre-commit hooks" are distinct from "Claude Code hooks" (PostToolUse/PreToolUse event hooks). This guide covers pre-commit hooks only. See ticket 04 for Claude Code hooks.

## Acceptance Criteria

```gherkin
Given the how-to guide exists at leafcutter-ai/docs/how-to/managing-pre-commit-hooks.md
When a developer follows the "create" section
Then they can add a new pre-commit hook script, register it in commit_guardian.json, and verify it fires on the next commit

Given the guide covers disable and delete operations
When a developer follows the "disable" section
Then they can set enabled: false in commit_guardian.json without deleting the hook script

Given the guide covers delete
When a developer follows the "delete" section
Then they know which files to remove and which registry entries to clean

Given the guide is authored
When it passes the doc frontmatter guard
Then it has valid frontmatter including type: how_to
```

## Sign-offs

- [x] documentation-expert — 2026-05-28 13:45
- [x] how-to-author — 2026-05-28 13:46
- [x] pr-reviewer — 2026-05-28 13:48
- [ ] commit
- [ ] pull-request

## Comments

### 2026-05-28 13:45 — documentation-expert (status: ok)
feedback-id: fb_2026-05-28_e1ebb3b8
Researched commit_guardian.json schema and canonical hook scripts directory. Authored docs/how-to/managing-pre-commit-hooks.md covering create, modify, disable, and delete operations. Included canonical-path callout (deprecated templates/commit-guardian/ warning), naming-collision note distinguishing pre-commit hooks from Claude Code hooks, and troubleshooting section. Frontmatter uses type: how_to, status: active, component: build_pipeline.

### 2026-05-28 13:46 — how-to-author (status: ok)
feedback-id: fb_2026-05-28_7d0931c3
Reviewed the guide against how-to style standards: task-oriented structure with numbered procedural steps, clear prerequisites section, per-operation headings (Create/Modify/Disable/Delete), verification checklist, and troubleshooting with concrete symptom-to-fix mapping. Frontmatter valid (type: how_to, status: active, components: build_pipeline). No structural changes needed — guide meets how-to documentation standards.

### 2026-05-28 13:48 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-28_6f939a84
All four Gherkin acceptance criteria verified: (1) guide exists at docs/how-to/managing-pre-commit-hooks.md, (2) Create section covers script authoring, commit_guardian.json registration, build.py regeneration, and test-commit verification, (3) Disable section uses enabled: false with re-run build.py, (4) Delete section names all three removal targets (script, config block, hooks_manifest entry). Frontmatter passes doc_frontmatter guard: type: how_to, status: active, component: build_pipeline, related_docs paths exist. Canonical-path callout and naming-collision note both present. Approved.

## Implementation Tasks

### documentation-expert / how-to-author

- [x] Read `leafcutter-ai/config/commit_guardian.json` and `leafcutter-ai/templates/scripts/commit_guardian/` to understand the current hook structure and configuration schema.
- [x] Document CRUD operations in `leafcutter-ai/docs/how-to/managing-pre-commit-hooks.md`:
  **Create:**
  1. Create a new Python script in `leafcutter-ai/templates/scripts/commit_guardian/<hook-name>.py`.
  2. Add an entry to `commit_guardian.json` with `id`, `script`, `enabled: true`, and any required parameters.
  3. Register the hook in the hooks manifest so `build.py` deploys it.
  4. Run `build.py` and verify the hook appears in the target project's `.git/hooks/` or equivalent location.
  5. Test the hook with a commit that should trigger it.

  **Modify:**
  1. Edit the script in `templates/scripts/commit_guardian/`.
  2. Adjust parameters in `commit_guardian.json` if needed.
  3. Re-run `build.py`.

  **Disable (without deleting):**
  1. Set `"enabled": false` in `commit_guardian.json` for the hook entry.
  2. Re-run `build.py`.

  **Delete:**
  1. Remove the script from `templates/scripts/commit_guardian/`.
  2. Remove the entry from `commit_guardian.json`.
  3. Remove from hooks manifest.
  4. Run `build.py --clean` (post ticket 12) to remove the deployed artifact.
- [x] Add a "Canonical path" callout box explaining that `templates/commit-guardian/` is deprecated — use `templates/scripts/commit_guardian/` only.
- [x] Add "Naming collision note": pre-commit hooks (git hooks) vs Claude Code hooks (agent event hooks) are different systems. Link to how-to guide for Claude Code hooks (ticket 04).
- [x] Ensure the doc has valid frontmatter (type: how_to).

## Risk & Safety

- Touches money? No.
- Touches data? No — documentation only.
- Reversibility? Fully reversible.
