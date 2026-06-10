---
description: |
  Invoke the IT Product Owner agent for technical enrichment of AC YAML files.
  Adds assigned_agent, it_requirements, estimated_complexity, delivers_to/expects_from
  contracts, and doc_links to existing L2/L3 ACs. Operates AFTER BA has produced
  behavioral ACs. Uses architecture docs to understand the technical landscape.
  Use after /ba has produced L2/L3 ACs, or to enrich existing ACs with technical detail.
---

Invoke the `it-po` agent with the following context:

**User request:** $ARGUMENTS

**Instructions for the IT PO agent:**

1. Read the L2/L3 ACs the user references (or scan `docs/acceptance-criteria/` to find them).
2. For each AC, enrich with technical fields:
   - `assigned_agent`: which agent should implement this (python-coder, sql-coder, llm-expert, etc.)
   - `estimated_complexity`: S/M/L/XL
   - `delivers_to` / `expects_from`: inter-agent contracts
   - `doc_links`: references to architecture docs, ADRs, how-tos
   - `it_requirements`: any technical constraints or dependencies
3. Read architecture docs at `docs/architecture/` to understand component boundaries.
4. Split ACs when technical boundaries reveal multi-agent work (one AC should map to one agent).
5. Do NOT modify the `criteria` field — that belongs to the BA.
6. Set `origin_agent: it-po` on any new ACs you create (splits only).
7. Present enrichments to the user for review before writing.
