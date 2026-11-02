---
title: The clearing guide explains each refusal of remove
date: "2026-11-02"
time: "08:00"
type: manual
components: 
  - worktree_manager
  - build_orchestration
summary: "The clear-a-workspace how-to now says what to do when clearing is refused for a running program, a half-cleared workspace, a folder with no record or a detached workspace, and the answer reference lists each of those refusals by code and fields."
description: "BO-4300e-5-i. docs/how-to/clear-a-workspace.md gains four sections (no manual deletion steps; a detached workspace's unsent commit is delivered to its own branch or through a pull request into main, the only places remove counts as delivered). docs/reference/workspace-maker-answer.md gains a Refusals of remove section with the six refusals, their codes, fields and message openings, plus an example taken from the half-cleared test. New doc test unit_tests/build_orchestration/test_bo_4300e_5_i_docs.py ties the documented codes, fields and messages to the remove sources. BO-4300e-5-i and its parent BO-4300e-5 are done."
breaking: false
---

## Entry
