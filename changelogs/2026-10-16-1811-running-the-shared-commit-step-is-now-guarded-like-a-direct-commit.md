---
title: Running the shared commit step is now guarded like a direct commit
date: "2026-10-16"
time: "18:11"
type: manual
components: 
  - build_orchestration
  - git_vcs_operations
  - commit_guardian
summary: "Running the shared commit step from anywhere other than the commit agent is now blocked, just like a direct git commit."
description: "1 commit (7dbfa8a69). The commit-delegation PreToolUse hook (templates/hooks/enforce_commit_delegation.py) now blocks a run of commit_changes.py unless COMMIT_AGENT_MODE=1 is present, with the same message as a direct git commit; quoted mentions and readers such as cat stay allowed. templates/agents/commit.md step calls now carry the COMMIT_AGENT_MODE=1 prefix. Adds test_bo4500a_5_vii_step_is_guarded.py."
commits: 
  - 7dbfa8a69
breaking: false
---

## Entry
