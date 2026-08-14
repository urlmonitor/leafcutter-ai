# changelog

Portable-dev-workflow changelog write-path scripts.

## Purpose

This package provides `emit_entry.py`, the shared Python helper that writes
per-file changelog entries with YAML frontmatter. Both call sites funnel
through this helper:

- **Call site 1** (`changelog-agent`): standalone `/changelog` and `/prod-deploy` tail
- **Call site 2** (`epic-supervisor` Post-Completion Chain Step 2): `type=epic_completion`

The legacy `CHANGELOG.md` at the repo root is intentionally untouched; this
package only creates new files in the configured `changelog_folder`.

## Key Files

| File | Purpose |
|------|---------|
| `emit_entry.py` | CLI helper: validates payload, generates canonical filename, writes YAML frontmatter + body |
| `__init__.py` | Package marker (no public symbols) |

## Critical Context

- `emit_entry.py` requires no external dependencies (stdlib only).
- The `changelog_folder` is configured via `skills_config.json` key
  `changelog_folder` (default: `"changelogs/"`). The folder is created
  automatically on first write.
- Required frontmatter fields: `title`, `date`, `time`, `type`, `components`,
  `description`. `emit_entry.py` raises `ValueError` if any are absent.
- `type` must be one of: `epic_completion`, `deploy_tag`, `manual`, `rollback`.
- When `type=epic_completion`, the `epic` field is also required.
- Filename format: `YYYY-MM-DD-HHMM-<slug>.md`. Collision avoidance appends
  `-2`, `-3`, etc. before `.md`.

## Maintenance

- Tests live at `leafcutter/tests/test_emit_entry.py` (19 tests,
  all using `tempfile.TemporaryDirectory` for isolation).
- Run with: `python -m unittest leafcutter/tests/test_emit_entry.py`
- Entry format: one file per entry under `changelogs/`, named
  `YYYY-MM-DD-HHMM-<slug>.md` with YAML frontmatter. See `emit_entry.py`.
