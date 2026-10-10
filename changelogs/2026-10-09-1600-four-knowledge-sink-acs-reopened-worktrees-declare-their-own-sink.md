---
title: "Four knowledge-sink ACs reopened: every worktree declares its own sink"
date: "2026-10-09"
time: "16:00"
type: manual
components: 
  - knowledge_system
  - infrastructure
summary: "INF-400c-4 and its children -i, -iii and -v were marked done, but the knowledge sink is still not shared across worktrees. They are reopened to todo with evidence, pending the INF-500d-4 feedback-sink feature."
description: "One content commit (7fbfd5b67), AC store only. BrainCandy decided on 2026-10-09 to set INF-400c-4, INF-400c-4-i, INF-400c-4-iii and INF-400c-4-v to work_status todo. Each gets an amended_by entry quoting the violated clause and the file:line evidence. The criteria are unchanged. Defect 1: setup_ticket_worktree.py runs build.py --target-dir <worktree> in every new worktree, so each worktree's deployed knowledge_sink.json names that worktree as the sink, and eight worktrees hold their own knowledge_emissions.jsonl. Defect 2: emit_event.py looks for <dir>/config/knowledge_sink.json, but the declaration lives under .leafcutter/config/, so it falls back to a bare relative path. All four return to done when INF-500d-4-iii and -iv land."
commits: 
  - 7fbfd5b67
breaking: false
---

## Entry

Four knowledge-sink ACs had been marked done while the sink they describe is still split
across worktrees. They are back to `todo` (BrainCandy, 2026-10-09):

- **INF-400c-4-i**: an agent in a worktree and an agent at the project root get two different
  sinks from `harvest_learnings.py --print-sink`.
- **INF-400c-4-iii**: `emit_event.py` never finds the declaration, because it looks for
  `<dir>/config/knowledge_sink.json` while the file is at `.leafcutter/config/`. It falls back
  to the relative `debugging/logs/agent_telemetry.jsonl`.
- **INF-400c-4-v**: the worktree bootstrap runs `build.py --target-dir <worktree>`, which gives
  every worktree a second sink. The NOTE the build prints never names the project it divides.
- **INF-400c-4**: the composite parent. Its own durability clauses fail too.

Each AC carries an `amended_by` entry with the file:line evidence and the observed paths.
The criteria are unchanged. The INF-500d-4 feedback-sink feature (INF-500d-4-iii and -iv) will
fix the behaviour, and the ACs go back to done when it lands. No code changes.
