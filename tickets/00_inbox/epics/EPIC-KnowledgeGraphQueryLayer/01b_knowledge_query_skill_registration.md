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
  python-coder: needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: needed
  pr-reviewer: needed
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

- [ ] AC-1: `templates/skills/knowledge-query/SKILL.md` exists, follows the same
  frontmatter schema as `templates/skills/roadmap-query/SKILL.md`, and documents all
  CLI flags (`--query`, `--surface`, `--format`, `--edges`, `--project-root`) with at
  least one example invocation per flag.
- [ ] AC-2: An entry for `knowledge-query` is present in `config/skill_registry.json`
  with `portable: true` and `template_path: "leafcutter/templates/skills/knowledge-query/"`.

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

- [ ] AC-3: `templates/skills/knowledge-query/SKILL.md` documents exactly the CLI flags
  that `knowledge_query.py` implements — no undocumented flags, no documented flags that
  do not exist in the script.
- [ ] AC-4: A "Knowledge Query" row is present in the Architecture Reference table in
  `CLAUDE.md` pointing to the skill doc path.
- [ ] AC-5: A row in `docs/INDEX.md` for the new skill.
- [ ] AC-6: `SKILL.md` is consistent with the implemented script (no undocumented or
  missing flags).

**Depends on python-coder:** skill template path and CLI flags from the Delivers-to block above.

#### Tasks

1. Verify SKILL.md consistency with implemented CLI flags.
2. Add row to `docs/INDEX.md` for the new skill if not auto-generated.
3. Add "Knowledge Query" entry to CLAUDE.md Architecture Reference table.

## AC Coverage

| AC   | Test | Implementation | Validated |
|------|------|----------------|-----------|
| AC-1 |      |                |           |
| AC-2 |      |                |           |
| AC-3 |      |                |           |
| AC-4 |      |                |           |
| AC-5 |      |                |           |
| AC-6 |      |                |           |

## Sign-offs

- [ ] python-coder
- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Risk & Safety

- Touches money? No.
- Touches data? No — skill registration only. No runtime data is modified.
- Reversibility? The skill entry in `skill_registry.json` can be removed
  without breaking anything else. The SKILL.md template is additive.
- Risk of regressions: low. Adding a new skill does not affect existing skills
  or the build pipeline.
