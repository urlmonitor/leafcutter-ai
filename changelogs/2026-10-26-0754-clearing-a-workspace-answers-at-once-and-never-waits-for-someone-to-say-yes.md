---
title: Clearing a workspace answers at once and never waits for someone to say yes
date: "2026-10-26"
time: "07:54"
type: manual
components: 
  - worktree_manager
  - build_orchestration
summary: "The workspace maker's remove verb refuses before deleting anything when a program works inside the workspace (or the program check cannot run), finishes half-cleared workspaces, clears detached ones safely, and counts vanished files as gone."
description: "BO-4300e-2-iv to -viii. iv: the program check runs before any fetch, push or deletion, matches current folders by whole path, never kills, and fails closed. v/vi: asking again finishes a half-cleared workspace of this project; one still holding files needs the one-time token bound to exactly those files; a folder with no record is finished only when empty (user decision 2026-10-29). vii: a detached workspace is found by its location and its detached commit and recorded line are both checked for unsent work. viii: an item that vanishes while it is deleted counts as deleted; one that cannot be deleted is still named. New module templates/scripts/worktree_remove_checks.py. Wrong-version gate: every one of 24 named wrong versions caught."
breaking: false
---

## Entry
