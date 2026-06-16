---
description: |
  Slash-command surface for v2 ticket creation (parallel pipeline for testing).
  Dispatches the v2 pipeline: Opus BA + optional IT PO + new AC format.
  Produces tickets with per-agent contracts and ac_coverage frontmatter.
  v1 pipeline (create-ticket) is unmodified — this is a parallel test path.
---

<!-- v2 pipeline: business-analyst-v2 (Opus) → complexity routing → [it-po | refinement] → ticket with AC format -->
<!-- This command does NOT modify create-ticket, business-analyst, or any v1 templates. -->
<!-- See EPIC-ContractDrivenACs ticket 00_create_ticket_v2 for the testing strategy. -->

The `create-ticket-v2` agent was removed in EPIC-AcPipelineConsolidation v2.0.0. Use `/create-ticket` instead, which now runs the consolidated pipeline: $ARGUMENTS
