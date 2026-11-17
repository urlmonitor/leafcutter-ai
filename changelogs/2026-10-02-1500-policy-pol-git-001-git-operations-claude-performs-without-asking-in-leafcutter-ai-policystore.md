---
title: "Policy POL-GIT-001: git operations Claude performs without asking in leafcutter-ai (#PolicyStore)"
date: "2026-10-02"
time: "15:00"
type: manual
components: 
  - git_vcs_operations
  - decision_kernel
summary: "Records the user's approved policy of 2026-09-30: in leafcutter-ai, Claude and its agents commit, create branches and worktrees, push non-main branches and open pull requests without asking; merging to main, force-pushing and pushing to main still need the human's confirmation; anything unlisted asks first."
description: "The first learned human decision for the kernel and the seed example for ADR-054 open item 2. Location (docs/conventions/) and format are provisional; TICKET-20260930-PolicyStore owns the policy store and a deterministic permission-lookup port. V0 surfaces the record as internal_principles evidence through the repo.principles retrieval source; nothing enforces it at runtime yet."
---

## Entry
