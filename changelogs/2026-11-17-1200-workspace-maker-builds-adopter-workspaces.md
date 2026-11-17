---
title: "The workspace maker builds new workspaces in projects that keep leafcutter in a submodule"
date: "2026-11-17"
time: "12:00"
type: manual
components:
  - worktree_manager
  - build_orchestration
summary: "The workspace maker's install step ran <workspace>/scripts/build.py, which only exists in leafcutter's own repository. In a project that keeps leafcutter as a submodule (DIAGraph: <repo>/leafcutter/), every workspace was cloned and then refused BOOTSTRAP_FAILED 'scripts/build.py is absent', and the submodule was never fetched, so /build-feature could not start any epic there (seen on build v21.0.93). The maker now fetches the package submodule into the new workspace and runs the package's build from its real location, and a project may declare its own install command (workspace_install_command) when its install goes through a wrapper."
description: "BO-4300b-2-iii, BO-4300b-2-iv. New templates/scripts/worktree_install.py (deployed beside the maker), called by worktree_readiness.run_install_build. New key workspace_install_command in config/skills_config.schema.json and docs/reference/skills-config-fields.md. New tests unit_tests/build_orchestration/test_bo_4300b_2_iii.py and test_bo_4300b_2_iv.py run the deployed maker against real submodule, nested-folder, self-host and declared-command fixtures."
commits:
breaking: false
---

## Entry

In projects that install leafcutter as a submodule, asking for a new workspace always failed
after the copy was made, so no epic could be started. The workspace maker now finds leafcutter
where the project keeps it, fetches it into the new workspace, and builds from there. A project
whose install must go through its own wrapper can name that command in its settings.
