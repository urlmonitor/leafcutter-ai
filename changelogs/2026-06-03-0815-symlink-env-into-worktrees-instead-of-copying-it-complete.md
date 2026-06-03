---
title: Symlink .env into worktrees instead of copying it complete
date: "2026-06-03"
time: "08:15"
type: ticket_completion
components: 
  - build_pipeline
summary: "Worktree .env is now symlinked to the main repo instead of copied, keeping env vars in sync."
description: "Replace shutil.copy with os.symlink for .env in worktree bootstrap, keeping env vars in sync across all worktrees. Falls back to copy on Windows without symlink privilege."
pr: 33
commits: 
  - d104a06
  - 561490b
ticket: "TICKET-20260602-WorktreeEnvSymlink"
---

## Entry
