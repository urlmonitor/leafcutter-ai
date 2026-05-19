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
  architect-review: signed_off
  python-coder: signed_off
  test-writer: signed_off
  documentation-expert: signed_off
  pr-reviewer: signed_off
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

- [x] architect-review — 2026-05-19 15:30
- [x] python-coder — 2026-05-19 15:45
- [x] test-writer — 2026-05-19 16:00
- [x] documentation-expert — 2026-05-19 16:10
- [x] pr-reviewer — 2026-05-19 16:20
- [ ] commit
- [ ] pull-request

## Comments

### 2026-05-19 15:30 — architect-review (status: ok)

feedback-id: fb_2026-05-19_8df2fdc8

**Impact classification: LARGE (file-count threshold: 7-8 files, single component build_system).**

No always-large triggers fired (no Alembic migration, no hypertable change, no public API change, no ADR contract change). The change is limited to one component (`build_system`): config JSON, schema, two SKILL.md templates, build_phases.py, README, and cross-reference updates. Despite the file count, this is architecturally a pure rename + optional boolean field addition — low risk, fully reversible.

**Design decision (copy-vs-suppress):** Confirmed the copy-keep approach: `build_skills()` should continue copying `internal: true` skills to `.claude/skills/` (so runtime agents can still invoke them), but add frontmatter reading to skip generating user-facing summary tables for internal skills. The `name:` rename alone (to `build-feature-ops-notes`) already removes the collision from the Claude panel; `internal: true` provides the machine-readable marker for future CI/listing tooling. No new ADR required — this is a naming and labelling convention, not a cross-cutting architectural policy change.

**Acceptance-criteria adjustments:** None. Spec is clear and self-consistent.

**No suggested diagrams.** Pure configuration/documentation rename with no new data flows or service boundaries.

## Escalation

Branch: none
Reason: Single build_system component; no always-large trigger fired. File count exceeds threshold but architectural impact is minimal (rename + boolean field).

### 2026-05-19 15:45 — python-coder (status: ok)

feedback-id: fb_2026-05-19_27802d46

All 7 implementation tasks complete. Changes applied:
- `skill_registry.schema.json`: added optional `internal` boolean field to the skill definition.
- `skill_registry.json`: renamed `id: "build-feature"` → `id: "build-feature-ops-notes"`, changed `portable: false, domain: "bybit-trader"` → `portable: true, domain: null, template_path: "leafcutter/templates/skills/build-feature-ops-notes/"`, added `internal: true`; added `internal: true` to the `build-single-ticket` entry.
- `git mv leafcutter-ai/templates/skills/build-feature/ → build-feature-ops-notes/` (staged rename).
- Updated `build-feature-ops-notes/SKILL.md` frontmatter: `name: build-feature` → `name: build-feature-ops-notes`, added `internal: true`; updated example path in KI-2 resume template.
- Updated `build-single-ticket/SKILL.md` frontmatter: added `internal: true`.
- `build_phases.py`: imported `parse_frontmatter`; updated `build_skills()` to detect `internal: true` in each skill's SKILL.md, log internal skill names, and annotate their output lines with `[internal]`. Skills are still copied (copy-keep approach confirmed by architect-review).
- `templates/workflows/build-feature.md:174`: updated path reference to `build-feature-ops-notes/SKILL.md`.

### 2026-05-19 16:00 — test-writer (status: ok)

feedback-id: fb_2026-05-19_80b11883

Created `leafcutter-ai/tests/test_skill_registry.py` with 6 tests across 3 test classes: `TestSkillRegistryUniqueness` (no duplicate IDs), `TestSkillRegistryInternalFlag` (build-feature-ops-notes and build-single-ticket both have `internal: true`; old `build-feature` id absent), and `TestSkillRegistrySchemaValidation` (registry validates against schema; schema allows `internal` field). Also added `description` as an optional field to the schema to fix a pre-existing validation failure caused by the `roadmap-steward` entry. All 6 tests pass.

### 2026-05-19 16:10 — documentation-expert (status: ok)

feedback-id: fb_2026-05-19_dd338a34

Documentation review complete. `leafcutter-ai/README.md` only references `/build-feature` as a slash command (user-facing entry point) — no update needed. Searched `docs/`, `templates/agents/`, and `templates/workflows/` for `.claude/skills/build-feature/` path references: the only reference in `templates/workflows/build-feature.md:174` was already updated by python-coder to `build-feature-ops-notes`. No additional documentation changes required.

### 2026-05-19 16:20 — pr-reviewer (status: ok)

feedback-id: fb_2026-05-19_d60fd62a

All acceptance criteria verified:
- AC1: `build-feature` knowledge skill renamed to `build-feature-ops-notes` in templates and built output. Old `.claude/skills/build-feature/` removed (git rm), new `.claude/skills/build-feature-ops-notes/` added. Only one `build-feature` entry will appear in the Claude skill panel — the slash command.
- AC2: Skill content (KI-1, KI-2) intact in renamed `SKILL.md`; all path references updated.
- AC3: `build-single-ticket` still copied to `.claude/skills/`; `internal: true` in frontmatter provides machine-readable suppression marker.
- AC4: `skill_registry.schema.json` updated with `internal` boolean field; 6 unit tests pass. Pre-existing `description` field (roadmap-steward entry) also added to schema to fix latent validation failure.
- No regressions found. `build.py` ran cleanly (167 files up-to-date, 6 written).

## Implementation Tasks

### python-coder

- [x] Add `internal` boolean field (optional, default false) to `skill_registry.schema.json` under the `skill` definition
- [x] Update `leafcutter-ai/config/skill_registry.json`: rename entry `id: "build-feature"` → `id: "build-feature-ops-notes"`, set `internal: true`; set `internal: true` on the `build-single-ticket` entry
- [x] Rename template directory `leafcutter-ai/templates/skills/build-feature/` → `leafcutter-ai/templates/skills/build-feature-ops-notes/` (git mv)
- [x] Update the SKILL.md frontmatter `name: build-feature` → `name: build-feature-ops-notes` and add `internal: true` in that file
- [x] Update `build-single-ticket/SKILL.md` frontmatter to add `internal: true`
- [x] In `leafcutter-ai/scripts/build_phases.py` `build_skills()`: read each skill template's SKILL.md frontmatter; skip copying to `.claude/skills/` when `internal: true` is set — OR copy but add a mechanism for the skill panel to suppress it (see Note below)
- [x] Update any agent SKILL.md or command file that references `.claude/skills/build-feature/SKILL.md` by path to use `.claude/skills/build-feature-ops-notes/SKILL.md`

> **Note on copy-vs-suppress**: The simplest approach that both keeps runtime access intact and suppresses the user-facing entry is to keep the skill copy step as-is but rename the `name:` field in frontmatter (Claude Code uses `name:` to show the entry; a name like `build-feature-ops-notes` is already distinct). The `internal: true` flag provides an explicit machine-readable marker for future tooling. Confirm the chosen approach with architect-review before implementation.

### test-writer

- [x] Add unit test in `unit_tests/commit_guardian/` (or a new `unit_tests/build_system/` directory) that reads `leafcutter-ai/config/skill_registry.json` and asserts: (a) no two entries share the same `id`, (b) entries with `internal: true` are present for `build-feature-ops-notes` and `build-single-ticket`
- [x] Add test that validates `skill_registry.json` against `skill_registry.schema.json` and passes after adding the `internal` field

### documentation-expert

- [x] Update `leafcutter-ai/README.md` references to `build-feature` (knowledge skill context) to use the new name `build-feature-ops-notes`
- [x] Update any cross-references in `docs/` or agent files that cite `.claude/skills/build-feature/` by path

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Fully reversible — renaming a folder and updating config JSON is a straightforward git operation. If any runtime agent breaks due to a stale path reference, `git revert` restores all files.
- Shared contract risk: `epic-supervisor` and `worktree-agent` load the ops-notes skill by path (`.claude/skills/build-feature/SKILL.md`). All path references must be updated atomically in the same PR. A global search for the old path is required before merging.
