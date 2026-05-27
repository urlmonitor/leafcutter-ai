---
title: "Consolidated Output Root (.leafcutter/)"
date: "2026-05-27"
time: "12:00"
type: epic_completion
breaking: true
version: "0.1.0"
components:
  - build_pipeline
  - infrastructure
summary: "All build.py outputs consolidated into a single .leafcutter/ directory. Existing installs auto-migrate on rebuild."
description: "Completed EPIC-ConsolidatedOutputRoot. All build artifacts now write into .leafcutter/ instead of being scattered across .claude/, scripts/, config/, and the project root. A shim layer bridges external tool paths (.claude/agents/, .gemini/, .pre-commit-config.yaml) back via symlinks. Internal scripts live in .leafcutter/scripts/ with no shim. Stale files at old locations are auto-removed on upgrade."
---

## Breaking Changes

- **Output location moved**: All build.py artifacts now write to `.leafcutter/` instead of `.claude/`, `scripts/`, `config/`, and project root.
- **Pre-commit hook entry paths changed**: Hook entries now reference `.leafcutter/scripts/commit_guardian/...` instead of `scripts/commit_guardian/...`. Handled automatically by the build.
- **Stale file auto-removal**: On first build after upgrade, old files at `scripts/commit_guardian/`, `scripts/doc_compliance/`, `scripts/feedback/`, `.claude/agents/` (as directories) are removed and replaced by the new layout.

## Migration

Run `build.py` — it handles everything automatically:
1. Writes all artifacts to `.leafcutter/`
2. Removes stale files at old locations
3. Creates symlinks at canonical tool paths

No manual steps required. See `docs/how-to/output-layout/adopt-consolidated-output-root.md` for details.

## New Features

- `output_root` config field — controls output directory name (default: `.leafcutter`)
- `shim_strategy` config field — controls symlink vs copy behavior (`auto`/`symlink`/`copy`)
- `--migrate` flag — dry-run scan of stale files without deleting
- Auto-cleanup of pre-consolidation files on build
- ADR-004 documenting the architectural decision

## Files Added/Changed

- `docs/architecture/adrs/ADR-004-consolidated-output-root.md` (new)
- `docs/explanation/consolidated-output-root.md` (new)
- `docs/how-to/output-layout/adopt-consolidated-output-root.md` (new)
- `docs/reference/skills-config-fields.md` (new)
- `config/skills_config.schema.json` (added output_root, shim_strategy)
- `config/skills_config.default.json` (added output_root, shim_strategy)
- `scripts/build.py` (output_root routing, --migrate, auto-cleanup)
- `scripts/build_phases.py` (path updates for consolidated output)
- `scripts/build_helpers.py` (new install_shims implementation)
- `scripts/config_loader.py` (ConfigValidationError, shim_strategy validation)
- `templates/scripts/commit_guardian/commit_guardian.json` ({{config.output_root}} in entries)
