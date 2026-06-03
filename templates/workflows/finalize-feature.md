---
description: >
  Orchestrates the 6-step post-merge feature finalization sequence (open PR if
  missing, merge to main, sync local main, run tests, close tickets, remove
  worktree) with prompt() gates on all destructive steps. Primary path: the
  finalize-feature.js workflow script (Claude Code >= 2.1.154). Fallback path:
  the finalize-feature LLM agent (older versions).
---

# v2.1.154+: deterministic JS workflow (leaf workflow — no nested workflow() calls)
Invoke `finalize-feature.js` (Claude Code >= 2.1.154) or the `finalize-feature` agent (older versions) with: $ARGUMENTS
