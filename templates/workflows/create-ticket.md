---
description: |
  Slash-command surface for ticket creation.
  v2.1.154+: delegates to create-ticket.js (workflow script, flat depth-1 dispatch).
  <v2.1.154: falls back to the create-ticket agent directly.
---

<!-- v2.1.154+ path: handled by create-ticket.js workflow script -->
<!-- The JS workflow spawns business-analyst → architect-review (conditional) -->
<!-- all at depth 1, avoiding the nesting-depth violation. -->
<!-- See: docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md -->

<!-- Fallback path for Claude Code < v2.1.154 (no workflow script support): -->
<!-- The create-ticket agent was removed in EPIC-AcPipelineConsolidation v2.0.0. -->
<!-- For older Claude Code installs, please upgrade to v2.1.154+ to use the workflow script. -->
Please upgrade Claude Code to v2.1.154 or newer to use the /create-ticket workflow. Your request: $ARGUMENTS
