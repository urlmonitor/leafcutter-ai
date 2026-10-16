---
title: "Reference: Workspace Maker Deploy Entry"
description: "The WORKSPACE_MAKER_SCRIPTS deploy entries and their deployed paths for the one workspace maker (worktree.py); consult it when the maker or a module it imports is missing from a deployed install."
type: reference
status: active
created: 2026-10-16
last_updated: 2026-10-16
components:
  - worktree_manager
  - build_orchestration
related_docs:
  - docs/reference/workspace-maker-interface.md
  - docs/architecture/adrs/ADR-070-single-workspace-maker-and-resolver.md
---

> **Parent document:** [workspace-maker-interface.md](workspace-maker-interface.md)

# Workspace Maker Deploy Entry

Lookup tables for how the maker and its modules reach a deployed install. Source and deployed locations of each file are in the parent document's Locations table.

---

## Deploy Entry

Source: `scripts/build_phases_script_deploy.py` `WORKSPACE_MAKER_SCRIPTS`; consumed by `build_template_standalone_scripts` and mirrored in `scripts/build_deploy_manifest_helpers.py` (imports the same tuple, adding `scripts/<name>` to the deployed set and `templates/scripts/<name>` to the source set).

| Entry in `WORKSPACE_MAKER_SCRIPTS` | Deployed to |
|---|---|
| `worktree.py` | `<install>/scripts/worktree.py` |
| `workspace/__init__.py` | `<install>/scripts/workspace/__init__.py` |
| `workspace/workspace_root.py` | `<install>/scripts/workspace/workspace_root.py` |
| `workspace/workspace_core.py` | `<install>/scripts/workspace/workspace_core.py` |
| `workspace/workspace_checks.py` | `<install>/scripts/workspace/workspace_checks.py` |
| `workspace/workspace_create.py` | `<install>/scripts/workspace/workspace_create.py` |

| Behaviour | Rule |
|---|---|
| Missing source | A named entry whose source file is absent is recorded through `record_deploy_failure("build_template_standalone_scripts", ...)`. |
| Nested entries | Entries containing `/` are copied explicitly; the shallow `templates/scripts/*.py` glob does not reach them. |
| Overwrite | Compare-before-write; unchanged files are counted as up to date. |
