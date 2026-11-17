---
title: A stopped workspace clearing can be finished by asking again
date: "2026-11-03"
time: "11:35"
type: manual
components: 
  - worktree_manager
  - build_orchestration
summary: "remove now marks the record 'clearing' after its checks pass and deletes the record last, so a clearing stopped part-way finishes on a repeat request without a token. ensure and locate refuse such a leftover with the new code HALF_CLEARED; a workspace whose repository can no longer be read, and a record-less folder whose leftover .git names this project's hub, are treated as half-cleared."
description: "Fast-lane build of BO-4300e-2 (branch fastlane/bo-4300e-2). Built acceptance criteria: BO-4300e-2, BO-4300e-2-ix, BO-4300e-2-xi, BO-4300e-2-x, BO-4300e-2-xii. Files modified: docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300c-2.yaml, docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300e-2-ix.yaml, docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300e-2-x.yaml, docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300e-2-xi.yaml, docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300e-2-xii.yaml, docs/components.json, docs/how-to/clear-a-workspace.md, docs/reference/workspace-maker-answer.md, scripts/build_phases_script_deploy_standalone.py, templates/scripts/worktree.py, templates/scripts/worktree_admin.py, templates/scripts/worktree_answer.py, templates/scripts/worktree_ensure_steps.py, templates/scripts/worktree_remove.py, templates/scripts/worktree_remove_checks.py, templates/scripts/worktree_remove_half.py, unit_tests/build_orchestration/test_bo_4300e_2_ix.py, unit_tests/build_orchestration/test_bo_4300e_2_x.py, unit_tests/build_orchestration/test_bo_4300e_2_xi.py, unit_tests/build_orchestration/test_bo_4300e_2_xii.py."
breaking: false
---

## Entry
