---
description: |
  Slash-command surface for documentation-expert.
  Invoked by /documentation; the documentation-expert agent owns this workflow.
---

<!-- Canonical slash-command body for /documentation.
     This file is loaded by documentation-expert when invoked via /documentation.
     Do not modify this file to add system-prompt logic -- put that in
     .claude/agents/documentation-expert.md instead. -->

Pass the user's request to the `documentation-expert` agent. The agent will:

1. Read `docs/README.md` to anchor on the Diataxis genre-folder mapping.
2. Classify the request by Diataxis intent (do / decide-record / design / look up / understand).
3. Dispatch to the matching specialist sub-agent(s) sequentially.
4. Return a unified payload listing every doc file produced.

If the user has not yet provided a subject or description for the documentation,
ask: "What would you like to document? Please describe the subject and what kind
of doc you need (how-to, ADR, architecture, reference, or explanation)."
