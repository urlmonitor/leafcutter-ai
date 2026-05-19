---
title: "Disambiguate build-feature skill name collision and mark internal sub-skills"
status: todo
components:
  - build_system
created: 2026-05-19
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
agents:
  architect-review: needed
  python-coder: needed
  test-writer: needed
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
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

References: `.claude/skills/build-feature/SKILL.md`, `.claude/skills/build-single-ticket/SKILL.md`, `leafcutter-ai/config/skill_registry.json`, `leafcutter-ai/config/skill_registry.schema.json`, `leafcutter-ai/scripts/build_phases.py`.

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

- [ ] architect-review
- [ ] python-coder
- [ ] test-writer
- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### python-coder

- [ ] Add `internal` boolean field (optional, default false) to `skill_registry.schema.json` under the `skill` definition
- [ ] Update `leafcutter-ai/config/skill_registry.json`: rename entry `id: "build-feature"` → `id: "build-feature-ops-notes"`, set `internal: true`; set `internal: true` on the `build-single-ticket` entry
- [ ] Rename template directory `leafcutter-ai/templates/skills/build-feature/` → `leafcutter-ai/templates/skills/build-feature-ops-notes/` (git mv)
- [ ] Update the SKILL.md frontmatter `name: build-feature` → `name: build-feature-ops-notes` and add `internal: true` in that file
- [ ] Update `build-single-ticket/SKILL.md` frontmatter to add `internal: true`
- [ ] In `leafcutter-ai/scripts/build_phases.py` `build_skills()`: read each skill template's SKILL.md frontmatter; skip copying to `.claude/skills/` when `internal: true` is set — OR copy but add a mechanism for the skill panel to suppress it (see Note below)
- [ ] Update any agent SKILL.md or command file that references `.claude/skills/build-feature/SKILL.md` by path to use `.claude/skills/build-feature-ops-notes/SKILL.md`

> **Note on copy-vs-suppress**: The simplest approach that both keeps runtime access intact and suppresses the user-facing entry is to keep the skill copy step as-is but rename the `name:` field in frontmatter (Claude Code uses `name:` to show the entry; a name like `build-feature-ops-notes` is already distinct). The `internal: true` flag provides an explicit machine-readable marker for future tooling. Confirm the chosen approach with architect-review before implementation.

### test-writer

- [ ] Add unit test in `unit_tests/commit_guardian/` (or a new `unit_tests/build_system/` directory) that reads `leafcutter-ai/config/skill_registry.json` and asserts: (a) no two entries share the same `id`, (b) entries with `internal: true` are present for `build-feature-ops-notes` and `build-single-ticket`
- [ ] Add test that validates `skill_registry.json` against `skill_registry.schema.json` and passes after adding the `internal` field

### documentation-expert

- [ ] Update `leafcutter-ai/README.md` references to `build-feature` (knowledge skill context) to use the new name `build-feature-ops-notes`
- [ ] Update any cross-references in `docs/` or agent files that cite `.claude/skills/build-feature/` by path

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Fully reversible — renaming a folder and updating config JSON is a straightforward git operation. If any runtime agent breaks due to a stale path reference, `git revert` restores all files.
- Shared contract risk: `epic-supervisor` and `worktree-agent` load the ops-notes skill by path (`.claude/skills/build-feature/SKILL.md`). All path references must be updated atomically in the same PR. A global search for the old path is required before merging.
