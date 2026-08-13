---
title: "Fix worktree .env bootstrap FileExistsError on pre-existing symlink (BP-015)"
date: "2026-08-14"
time: "00:59"
type: manual
components: 
  - worktree_manager
summary: "Fixed a bug where creating a new ticket worktree could fail to set up its environment file, which was blocking developers from starting new work in a fresh worktree."
description: "_bootstrap() previously called os.symlink() without clearing the destination, so a worktree checkout whose .env was already a tracked symlink aborted with FileExistsError, and the shutil.copy fallback then raised shutil.SameFileError (or OSError: Too many levels of symbolic links for a self-referential link). _bootstrap() now removes any pre-existing .env entry first, checking is_symlink() before exists() so a broken or self-referential symlink is removed without being followed; an unlink failure logs a WARNING and continues instead of aborting, and shutil.SameFileError was added to the copy-fallback except clause as defence in depth. The fix is applied to BOTH copies of the script: scripts/setup_ticket_worktree.py (this repo's own checkout) and templates/scripts/setup_ticket_worktree.py, which build_template_standalone_scripts() deploys into consumer projects as scripts/setup_ticket_worktree.py — without the template mirror no consumer install would have received the fix. Covered by AC BP-015 and three behavioural tests in unit_tests/test_setup_ticket_worktree.py (two against the canonical copy, one against the template copy)."
---

## Entry
