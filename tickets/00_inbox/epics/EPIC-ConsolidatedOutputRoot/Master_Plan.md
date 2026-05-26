---
title: "EPIC: Consolidated Output Root (leafcutter-project/)"
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

# EPIC: Consolidated Output Root (leafcutter-project/)

Consolidate all `build.py` output artifacts — agents, skills, commands, hooks,
scripts, generated docs, `.pre-commit-config.yaml`, antigravity/gemini
instructions, and the build manifest — into a single `leafcutter-project/`
folder so they are isolated from the consumer project's own files rather than
scattered across `.claude/`, `scripts/`, `docs/`, and the project root.

The user's motivation: "I don't want to have the files spread out through
different places where they are mixed with proper project files."

## Open Questions (blocking design)

The following questions must be answered before the implementation tickets can
be fully hardened. The architect-review tickets (02 and 03) will not close
until these are resolved.

1. **Claude Code discovery path**: Does Claude Code require `.claude/agents/`
   and `.claude/skills/` to be physically present at those exact paths, or will
   it follow symlinks? Determines whether `leafcutter-project/` is the
   sole source-of-truth or whether physical copies must remain at `.claude/`.

2. **Folder name**: Should the output root be `leafcutter-project/`,
   `.leafcutter/`, `leafcutter-out/`, or another name? Affects `.gitignore`
   defaults and the self-hosting CLAUDE.md boundary.

3. **Commit vs gitignore**: Should `leafcutter-project/` be committed to the
   consumer repo (checked-in config) or git-ignored (build artifact requiring
   regeneration)?

## Sub-Tickets

| # | File | Description | Status |
|---|------|-------------|--------|
| 01 | [01_adr_output_layout.md](./01_adr_output_layout.md) | Author ADR for the new consolidated output layout decision | `[ ]` |
| 02 | [02_design_shim_layer.md](./02_design_shim_layer.md) | Design and prototype symlink/shim layer for paths that must stay at canonical locations | `[ ]` |
| 03 | [03_redirect_build_phases.md](./03_redirect_build_phases.md) | Redirect all build phase outputs into leafcutter-project/ root | `[ ]` |
| 04 | [04_update_config_schema.md](./04_update_config_schema.md) | Update skills_config.json schema to configure the output root name/path | `[ ]` |
| 05 | [05_migration_self_hosting.md](./05_migration_self_hosting.md) | Migrate the self-hosted repo (build-self.sh and ADR-001) to the new layout | `[ ]` |
| 06 | [06_docs_and_gitignore.md](./06_docs_and_gitignore.md) | Write how-to guide, explanation doc, and .gitignore template for the new layout | `[ ]` |
