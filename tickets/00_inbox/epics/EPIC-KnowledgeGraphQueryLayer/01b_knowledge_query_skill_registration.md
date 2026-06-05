---
title: "Register /knowledge-query skill — template and registry entry"
status: todo
components:
  - knowledge-management
created: 2026-06-04
depends_on:
  - tickets/00_inbox/epics/EPIC-KnowledgeGraphQueryLayer/01a_knowledge_query_script_core.md
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
ac_coverage: 0/6
files_touched:
  - templates/skills/knowledge-query/SKILL.md
  - config/skill_registry.json
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: signed_off
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
---

# Register /knowledge-query skill — template and registry entry

## Actor / Goal

In order to expose the `knowledge_query.py` script (built in ticket 01a) as an
invocable `/knowledge-query` skill within the leafcutter harness, we need to create
the skill template (`SKILL.md`) and register it in the skill registry. This is the
skill-registration half of the knowledge query feature; the script implementation
itself lives in ticket 01a.

## Context

The `/roadmap-query` skill provides the structural template: a `SKILL.md` with YAML
frontmatter, usage sections, and a corresponding entry in `config/skill_registry.json`
with `portable: true`. This ticket follows the same pattern for `/knowledge-query`.

The skill wraps the CLI invocation of `python scripts/knowledge_query.py` — same
purpose as `/roadmap-query` but for cross-surface knowledge.

## Agent Contracts

### python-coder

- [x] AC-1: `templates/skills/knowledge-query/SKILL.md` exists, follows the same
  frontmatter schema as `templates/skills/roadmap-query/SKILL.md`, and documents all
  CLI flags (`--query`, `--surface`, `--format`, `--edges`, `--project-root`) with at
  least one example invocation per flag. <!-- signed: python-coder -->
- [x] AC-2: An entry for `knowledge-query` is present in `config/skill_registry.json`
  with `portable: true` and `template_path: "leafcutter/templates/skills/knowledge-query/"`. <!-- signed: python-coder -->

**Delivers to documentation-expert:**
```json
{
  "skill_template": "templates/skills/knowledge-query/SKILL.md",
  "registry_entry": "config/skill_registry.json (key: knowledge-query)",
  "cli_flags": ["--query", "--surface", "--format", "--edges", "--project-root"]
}
```

#### Implementation guidance

**Skill template** — model on `templates/skills/roadmap-query/SKILL.md`. Required sections:
YAML frontmatter, `## When to Use`, `## Invocation`, `## Output Modes`, `## Surfaces Queried`,
`## Error Behaviour`.

**Registry entry** — insert alphabetically between `glossary-bootstrap` and `package-audit`.

---

### documentation-expert

- [x] AC-3: `templates/skills/knowledge-query/SKILL.md` documents exactly the CLI flags
  that `knowledge_query.py` implements — no undocumented flags, no documented flags that
  do not exist in the script. <!-- signed: documentation-expert -->
- [x] AC-4: A "Knowledge Query" row is present in the Architecture Reference table in
  `CLAUDE.md` pointing to the skill doc path. <!-- signed: documentation-expert -->
- [x] AC-5: A row in `docs/INDEX.md` for the new skill. <!-- signed: documentation-expert -->
- [x] AC-6: `SKILL.md` is consistent with the implemented script (no undocumented or
  missing flags). <!-- signed: documentation-expert -->

**Depends on python-coder:** skill template path and CLI flags from the Delivers-to block above.

#### Tasks

1. Verify SKILL.md consistency with implemented CLI flags.
2. Add row to `docs/INDEX.md` for the new skill if not auto-generated.
3. Add "Knowledge Query" entry to CLAUDE.md Architecture Reference table.

## AC Coverage

| AC   | Test | Implementation | Validated |
|------|------|----------------|-----------|
| AC-1 |      | Created templates/skills/knowledge-query/SKILL.md with all 5 CLI flags documented with example invocations | |
| AC-2 |      | Added knowledge-query entry to config/skill_registry.json (portable: true, template_path set) | |
| AC-3 |      | Verified SKILL.md documents exactly --query, --surface, --format, --edges, --project-root — matches knowledge_query.py --help output | |
| AC-4 |      | Added Knowledge Query row to CLAUDE.md Architecture Reference table | |
| AC-5 |      | Added knowledge-query and roadmap-query rows to docs/INDEX.md Skills section | |
| AC-6 |      | Cross-checked SKILL.md sections against knowledge_query.py --help: all 5 flags present, no extras documented | |

## Sign-offs

- [x] python-coder — 2026-06-05 10:00
- [x] documentation-expert — 2026-06-05 10:05
- [x] pr-reviewer — 2026-06-05 10:10
- [ ] commit
- [ ] pull-request

## Comments

### 2026-06-05 10:00 — python-coder (status: ok)
feedback-id: fb_2026-06-05_70249e20
completion_manifest:
  skill_template_created: true
  registry_entry_added: true
Created templates/skills/knowledge-query/SKILL.md following the roadmap-query pattern with all 5 CLI flags (--query, --surface, --format, --edges, --project-root) documented with example invocations. Added knowledge-query entry to config/skill_registry.json with portable: true, alphabetically between glossary-bootstrap and package-audit.

### 2026-06-05 10:05 — documentation-expert (status: ok)
feedback-id: fb_2026-06-05_61c21f32
completion_manifest:
  flag_accuracy_verified: true
  claude_md_updated: true
  index_md_updated: true
  skill_consistency_verified: true
Verified SKILL.md documents exactly the 5 CLI flags from knowledge_query.py --help (no extras, no missing). Added Knowledge Query row to CLAUDE.md Architecture Reference table. Added Skills section with knowledge-query and roadmap-query rows to docs/INDEX.md.

### 2026-06-05 10:10 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-05_e862ac58
completion_manifest:
  ac1_skill_template_correct: true
  ac2_registry_entry_correct: true
  ac3_flags_exact_match: true
  ac4_claude_md_row_present: true
  ac5_index_md_row_present: true
  ac6_consistency_verified: true
All 6 ACs satisfied. SKILL.md has correct frontmatter schema and all 5 flags with examples. Registry entry has portable: true and correct template_path. CLAUDE.md Architecture Reference updated. docs/INDEX.md Skills section added. No regressions to existing skills or docs.

## Risk & Safety

- Touches money? No.
- Touches data? No — skill registration only. No runtime data is modified.
- Reversibility? The skill entry in `skill_registry.json` can be removed
  without breaking anything else. The SKILL.md template is additive.
- Risk of regressions: low. Adding a new skill does not affect existing skills
  or the build pipeline.
