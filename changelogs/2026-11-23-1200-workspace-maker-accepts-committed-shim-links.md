---
title: "The workspace maker accepts hook settings a project committed as a link into its own install"
date: "2026-11-23"
time: "12:00"
type: manual
components:
  - worktree_manager
  - build_orchestration
summary: "A project that commits .pre-commit-config.yaml as a git symlink to .leafcutter/pre-commit-config.yaml (DIAGraph, created by an earlier build under the default 'auto' shim strategy) could never get a workspace: the maker builds with copies, its restore step then puts the committed link back to keep the tree unchanged, and the readiness check install_paths_regular refused that very link, so every ensure answered VERIFY_FAILED and /build-feature could start no epic there (seen on v21.0.121, after #1445). The check now accepts a link only when HEAD records it as that same symlink, it is relative, and it leads through no further link to an ordinary file inside the workspace. Junctions, absolute links, links leading out of the workspace and links the build leaves behind are still refused."
description: "BO-4300b-4-i. templates/scripts/worktree_readiness.py gains committed_inner_link, used by install_paths_regular. docs/reference/workspace-maker-answer.md states the exception. New test unit_tests/build_orchestration/test_bo_4300b_4_i.py runs the deployed maker against a real committed relative link (ready), a committed link out of the workspace and a committed absolute link (both refused)."
commits:
breaking: false
---

## Entry

Projects that keep their hook settings file in version control as a link into their leafcutter
install could not get a workspace: the maker put the link back to keep the copy unchanged, then
refused it. The maker now accepts such a link when the project committed it and it stays on an
ordinary file inside the workspace. Every other link is still refused.
