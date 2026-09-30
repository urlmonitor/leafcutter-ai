---
title: "Every worktree-creating subcommand uses the same repository resolution (ACD-2100a-2-ii)"
date: "2026-09-30"
time: "11:01"
type: manual
components: 
  - ac_driven_dev
summary: "Fixed AC and fast-lane worktree creation so they no longer crash when run from the self-hosted development layout."
description: "1 commit (27966cb1) to templates/scripts/setup_ticket_worktree.py: cmd_create_ac_worktree() and cmd_create_fastlane_worktree() now call _resolve_repository_with_search_fallback() instead of a bare _git_toplevel(), matching cmd_create_only()'s existing usage from ACD-2100a-2. In the ADR-001 self-hosting layout <repo>/.leafcutter is a symlink outside any git repository, so the anchor-only lookup made git exit 128; the fallback now performs a bounded search of cwd's immediate subdirectories and announces a search-based hit on stderr at WARNING. Added behavioural coverage across unit_tests/ac_driven_dev/test_acd_2100a_2_ii.py and test_acd_2100a_2_ii_more.py exercising each subcommand's resolution path with the script's own directory placed outside any git repository; both mutation-proven red without the fix. New AC ACD-2100a-2-ii recorded under ACD-2100a-2, work_status done."
commits: 
  - 27966cb1fd71af4cdd49a5f15b03c9d0a81bcbf6
breaking: false
---

## Entry
