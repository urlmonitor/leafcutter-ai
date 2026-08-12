---
title: "perf(build): scan AC store once for agent-card generation"
date: "2026-08-12"
time: "15:30"
type: fix
components: 
  - build_pipeline
summary: "The agent-cards build phase no longer re-walks and re-parses the entire AC store once per agent; it scans the store a single time and groups active ACs by assigned_agent, turning an O(agents x ac_files) cost into O(ac_files)."
description: "generate_agent_cards.build_agent_cards() called _scan_ac_assignments() once per agent, each doing a full os.walk + yaml.safe_load of the whole AC store — ~59 agents x 2714 AC YAML files = ~160k parses = ~13 min at 99% CPU with no output, which hung build.py's Agent-cards phase during AC-worktree bootstrap. Added _scan_all_ac_assignments() to walk the store once and group active ACs by assigned_agent (each group sorted by id); build_agent_cards() builds this index once (skipped in dry-run) and looks up per agent. Grouped output is byte-identical to the per-agent path; ~16s vs ~775s (~48x). _scan_ac_assignments() left intact for its direct-call unit tests. 18 unit tests pass. Merged via PR #420."
pr: 420
commits: 
  - ba47cb0d8
---

## Entry

Fixes a CPU-bound hang in `build.py`'s agent-card generation phase that made
AC-worktree bootstrap (and any large-store build) take 12+ minutes. See the
description above for the O(agents × ac_files) → O(ac_files) change.
