---
title: "Disambiguate build-feature skill name collision and mark internal sub-skills"
status: done
components:
  - build_pipeline
created: 2026-05-19
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
agents:
  architect-review: signed_off
  python-coder: signed_off
  test-writer: signed_off
  documentation-expert: signed_off
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: not_needed
---

# Disambiguate build-feature skill name collision and mark internal sub-skills

## Actor / Goal

In order to give new adopters a clear, unambiguous list of user-invocable skills after setup, we need to rename the `build-feature` knowledge/ops-notes skill to `build-feature-ops-notes` and mark `build-single-ticket` as internal-only, so that only one `build-feature` entry appears in the available-skills panel.

## Context

After a fresh `build.py` run, Claude Code's skill panel surfaces every `SKILL.md` found under `.claude/skills/` using the `name:` field from the file's YAML frontmatter. Today this produces three entries that look like build-feature commands:

1. `build-feature` — the knowledge/ops-notes skill (`leafcutter-ai/templates/skills/build-feature/SKILL.md`, `name: build-feature`) that documents failure modes and recovery procedures. It is read by `epic-supervisor` and `worktree-agent` at runtime but is **not** a user-invocable entry point.
2. `build-feature` — the actual user-facing slash command (`.claude/commands/build-feature.md`), which resolves an epic or ticket path and dispatches the right supervisor.
3. `build-single-ticket` — a sub-skill invoked automatically by `/build-feature` when the argument is a standalone ticket. Its description already says "Invoked by /build-feature" but it still appears in the panel.

The name collision between (1) and (2) is the primary pain point: both entries say `build-feature` with different descriptions, and users cannot tell which is the real entry point. The presence of (3) adds a second source of confusion.

The fix has three parts:
- **Rename** the knowledge skill from `build-feature` to `build-feature-ops-notes` (folder rename + `name:` + `id:` updates).
- **Add `internal: true`** to the SKILL.md frontmatter of `build-single-ticket` (and to `build-feature-ops-notes`) so the build pipeline can filter them from user-facing listings.
- **Extend the schema and build pipeline** to understand `internal: true` and skip those skills when generating user-facing skill summaries.

References: `.claude/skills/build-feature-ops-notes/SKILL.md`, `.claude/skills/build-single-ticket/SKILL.md`, `leafcutter-ai/config/skill_registry.json`, `leafcutter-ai/config/skill_registry.schema.json`, `leafcutter-ai/scripts/build_phases.py`.

## Acceptance Criteria

```gherkin
Given a project with a fresh build.py run (or existing .claude/skills/ output)
When the user opens the Claude Code skill panel
Then exactly one entry named "build-feature" appears
And that entry corresponds to the /build-feature slash command, not the ops-notes skill

Given the knowledge skill has been renamed to build-feature-ops-notes
When epic-supervisor or worktree-agent loads the skill by name
Then they still find and read the skill content without error
And all existing KI references (KI-1, KI-2) are intact

Given build-single-ticket has internal: true in its frontmatter
When build_phases.py copies skills to .claude/skills/
Then build-single-ticket is still copied (runtime agents must be able to invoke it)
But it is excluded from any user-facing "available skills" listing or summary table

Given skill_registry.schema.json is updated
When a CI validator runs against skill_registry.json
Then entries with internal: true pass validation without error
```

## Sign-offs

- [x] architect-review
- [x] python-coder
- [x] test-writer
- [x] documentation-expert
- [x] pr-reviewer
- [x] commit
- [x] pull-request

## Comments

### architect-review — 2026-05-19 (status: ok)

Classified as LARGE by file count (7-8 files) but single `build_system` component.
Confirmed copy-keep approach for `internal: true` skills: skills are still copied to
`.claude/skills/` for runtime access; the `name:` field rename plus `internal: true`
frontmatter flag disambiguates the user-facing panel. No ADR required.

### python-coder — 2026-05-19 (status: ok)

Implemented all tasks:
- `skill_registry.schema.json`: added optional `internal` boolean + `description` field
- `skill_registry.json`: renamed `build-feature` → `build-feature-ops-notes`, added `internal: true` to both entries
- Renamed template + deployed skill directories (`build-feature/` → `build-feature-ops-notes/`)
- Updated SKILL.md frontmatter in both renamed locations
- Added `internal: true` to `build-single-ticket/SKILL.md`
- Updated path references in `build-feature.md` command and workflow template

### test-writer — 2026-05-19 (status: ok)

Created `leafcutter-ai/tests/test_skill_registry.py` with 6 unit tests across 3 classes:
- `TestSkillRegistryUniqueness`: no duplicate IDs in registry
- `TestSkillRegistryInternalFlag`: `build-feature-ops-notes` and `build-single-ticket` have `internal: true`; old `build-feature` ID is absent
- `TestSkillRegistrySchemaValidation`: registry validates against schema; schema accepts `internal` field
All 6 tests pass.

### documentation-expert — 2026-05-19 (status: ok)

Verified all cross-references updated. Path references in `.claude/commands/build-feature.md`
and `leafcutter-ai/templates/workflows/build-feature.md` updated to new path.

### pr-reviewer — 2026-05-19 (status: ok)

All 4 acceptance criteria verified. No regressions.

### commit — 2026-05-19 (status: ok)

Committed as `5c439ad` on `main`. Clean 4-file commit after manual recovery from
over-scoped supervisor commit.

### pull-request — 2026-05-19 (status: not_needed)

No remote configured. Work committed directly to `main`.

## Implementation Tasks

### python-coder

- [x] Add `internal` boolean field (optional, default false) to `skill_registry.schema.json` under the `skill` definition
- [x] Update `leafcutter-ai/config/skill_registry.json`: rename entry `id: "build-feature"` → `id: "build-feature-ops-notes"`, set `internal: true`; set `internal: true` on the `build-single-ticket` entry
- [x] Rename template directory `leafcutter-ai/templates/skills/build-feature/` → `leafcutter-ai/templates/skills/build-feature-ops-notes/` (git mv)
- [x] Update the SKILL.md frontmatter `name: build-feature` → `name: build-feature-ops-notes` and add `internal: true` in that file
- [x] Update `build-single-ticket/SKILL.md` frontmatter to add `internal: true`
- [x] In `leafcutter-ai/scripts/build_phases.py` `build_skills()`: read each skill template's SKILL.md frontmatter; skip copying to `.claude/skills/` when `internal: true` is set — OR copy but add a mechanism for the skill panel to suppress it (see Note below)
- [x] Update any agent SKILL.md or command file that references `.claude/skills/build-feature/SKILL.md` by path to use `.claude/skills/build-feature-ops-notes/SKILL.md`

### test-writer

- [x] Add unit test in `leafcutter-ai/tests/` that reads `leafcutter-ai/config/skill_registry.json` and asserts: (a) no two entries share the same `id`, (b) entries with `internal: true` are present for `build-feature-ops-notes` and `build-single-ticket`
- [x] Add test that validates `skill_registry.json` against `skill_registry.schema.json` and passes after adding the `internal` field

### documentation-expert

- [x] Update cross-references in command and workflow files that cite `.claude/skills/build-feature/` by path

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Fully reversible — renaming a folder and updating config JSON is a straightforward git operation. If any runtime agent breaks due to a stale path reference, `git revert` restores all files.
- Shared contract risk: `epic-supervisor` and `worktree-agent` load the ops-notes skill by path (`.claude/skills/build-feature-ops-notes/SKILL.md`). All path references were updated atomically.
