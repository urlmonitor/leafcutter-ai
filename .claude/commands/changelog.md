---
name: changelog
description: |
  Standalone changelog and release notes generator. Reads git log between two
  refs (or from last deployment tag to HEAD), categorizes commits by file path
  and conventional-commit prefixes, and writes a new per-file changelog entry
  with YAML frontmatter via emit_entry.py. Does NOT modify the legacy CHANGELOG.md.
  For on-demand changelog generation without a full deployment. Also invoked
  automatically by /prod-deploy to create deployment tags.
---

# /changelog

Changelog and release notes workflow.

## Usage

```
/changelog                        # Generate entry from last deploy-* tag to HEAD
/changelog <from> <to>            # Custom range (any git refs)
/changelog --dry-run              # Show what would be written without modifying files
```

## What It Does

1. Finds the last `deploy-*` tag (or uses the specified range)
2. Collects all commits in the range with file-change stats
3. Categorizes commits using rules from `` (if the file exists); falls back to conventional-commit prefix heuristics when absent
4. Reads `docs/components.json` to select relevant registered component IDs
5. Writes a new per-file entry to `docs/changelog/` via `emit_entry.py`
6. Does NOT create a deployment tag (that is the job of `/prod-deploy`)
7. Does NOT write to or modify the legacy `CHANGELOG.md`

## Output Format

Each entry is a Markdown file at `docs/changelog/YYYY-MM-DD-HHMM-<slug>.md`:

```yaml
---
title: "Deploy deploy-2026-05-13-1 — live_trader improvements"
date: "2026-05-13"
time: "14:30"
type: deploy_tag
components:
  - live_trader
  - infrastructure
summary: "Released live trader improvements and infrastructure fixes."
description: "N commits covering trading improvements and infrastructure fixes."
commits:
  - abc1234
  - def5678
pr: "https://github.com/org/repo/pull/123"
adrs:
  - ADR-019
diagrams:
  - docs/architecture/pipeline.md
---

## Entry
```

The `summary` field is required and must be written in plain business language
(one sentence, accessible to non-engineers). The optional `pr`, `adrs`, and
`diagrams` fields can be added when the entry corresponds to a single merged
pull request or when the commits relate to architectural decisions or diagrams.

## Entry Types

| Type | When | Invoked by |
|------|------|-----------|
| `deploy_tag` | After a successful prod-deploy that created a tag | `/prod-deploy` → `changelog-agent` |
| `manual` | Standalone `/changelog` with a custom ref range | User directly |
| `epic_completion` | After every epic completes | `epic-supervisor` Step 2 |
| `rollback` | After a rollback operation | `/rollback` (if implemented) |

## Categorization

Categorization rules are loaded from ``
(default: `.claude/changelog_categories.md`). Create that file in your project
with a Markdown table mapping folder paths to category names. Example:

```markdown
| Category | Rule |
|----------|------|
| Trading | Files in `live_trader/` |
| Data Pipeline | Files in `collector/` or `data_collector/` |
| Database | Files in `sql_functions/`, `alembic/`, `models/` |
```

If the file does not exist, the agent uses only conventional-commit prefix
heuristics (`feat:` → Features, `fix:` → Bug Fixes, `docs:` → Documentation,
`chore:` → Maintenance, `refactor:` → Refactoring, `test:` → Tests,
`perf:` → Performance; unlabeled commits → Other).

Conventional commit prefixes always take precedence over file-path rules
when both are available.

## Migration Note

The legacy `CHANGELOG.md` at the repo root is intentionally left in place. This
workflow writes only new per-file entries and does not migrate or modify existing
content. A separate follow-up ticket will handle migration once the new write path
is validated in production.

## Related

- `changelog-agent` — the underlying agent (Call site 1)
- `epic-supervisor` Post-Completion Chain Step 2 — Call site 2 (`type: epic_completion`)
- `/prod-deploy` — creates deployment tags (called by that workflow, not by this one)
- `emit_entry.py` — the shared Python write path at `leafcutter/scripts/changelog/emit_entry.py`
- `ADR-019-changelog-entry-format.md` — decision record for the file-per-entry format
