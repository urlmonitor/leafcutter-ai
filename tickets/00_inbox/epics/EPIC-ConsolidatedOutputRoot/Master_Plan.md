---
title: "EPIC: Consolidated Output Root (.leafcutter/)"
type: epic
status: todo
components:
  - build_pipeline
  - config_loader
created: 2026-05-26
depends_on: []
priority: high
requires_diagram: true
requires_adr: true
---

# EPIC: Consolidated Output Root (.leafcutter/)

Consolidate all `build.py` output artifacts — agents, skills, commands, hooks,
scripts, generated docs, `.pre-commit-config.yaml`, antigravity/gemini
instructions, and the build manifest — into a single `.leafcutter/`
folder so they are isolated from the consumer project's own files rather than
scattered across `.claude/`, `scripts/`, `docs/`, and the project root.

The user's motivation: "I don't want to have the files spread out through
different places where they are mixed with proper project files."

## Open Questions (resolved)

1. **Claude Code discovery path**: Claude Code requires `.claude/agents/` and
   `.claude/skills/` at those exact paths. The shim layer must ensure those
   canonical paths exist (via symlink or file copy). To be empirically verified
   by the ADR author in ticket 01.

2. **Folder name**: **`.leafcutter/`** (hidden dot-prefix, follows `.claude/`
   and `.gemini/` convention). All tickets should use `.leafcutter/` instead of
   `.leafcutter/`.

3. **Commit vs gitignore**: **Configurable per consumer project.** The ADR
   should recommend git-ignored (build artifact) as the default posture but
   document both approaches. A `gitignore_output` config key or `.gitignore`
   template should be provided.

## Sub-Tickets

| # | File | Description | Status |
|---|------|-------------|--------|
| 01 | [01_adr_output_layout.md](./01_adr_output_layout.md) | Author ADR for the new consolidated output layout decision | `[ ]` |
| 02 | [02_design_shim_layer.md](./02_design_shim_layer.md) | Design and prototype symlink/shim layer for paths that must stay at canonical locations | `[ ]` |
| 03 | [03_redirect_build_phases.md](./03_redirect_build_phases.md) | Redirect all build phase outputs into .leafcutter/ root | `[ ]` |
| 04 | [04_update_config_schema.md](./04_update_config_schema.md) | Update skills_config.json schema to configure the output root name/path | `[ ]` |
| 05 | [05_migration_self_hosting.md](./05_migration_self_hosting.md) | Migrate the self-hosted repo (build-self.sh and ADR-001) to the new layout | `[ ]` |
| 06 | [06_docs_and_gitignore.md](./06_docs_and_gitignore.md) | Write how-to guide, explanation doc, and .gitignore template for the new layout | `[ ]` |
| 07 | [07_internal_paths_stay_at_root.md](./07_internal_paths_stay_at_root.md) | Keep internal-only outputs (scripts/, config/, rules/) at target_root — no shim needed | `[ ]` |
