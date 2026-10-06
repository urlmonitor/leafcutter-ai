---
title: "Generated agent cards outgrow the doc-length ratchet on every regeneration"
status: todo
components:
  - build_pipeline
  - commit_guardian
created: 2026-10-06
depends_on: []
priority: low
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - agent-cards
  - file-size
  - generated
last_updated: 2026-10-06
agents:
  python-coder: needed
  commit: needed
---

# Generated agent cards outgrow the doc-length ratchet on every regeneration

## Actor / Goal
In order to regenerate agent cards without a hook override, we need generated
`docs/agents/cards/*.card.md` files and the doc-length ratchet (`check-doc-length`, which reuses
the GE-127b-1 ratchet code) to stop conflicting.

## Context
- The cards are build output (`scripts/generate_agent_cards.py`). Several are far over the doc
  limit; `python-coder.card.md` is about 2500 lines. They grow every time an AC is assigned to
  that agent, because each card lists its ACs.
- The ratchet only lets an over-limit file shrink, and splitting a card by hand does not survive
  the next build. So every regeneration needs `SKIP=check-doc-length`.
- **Hit 2026-10-06** while committing TICKET-20261002-WorktreeBootstrapLeavesTrackedFilesDirty,
  which regenerated 4 stale cards. The user chose a one-off skip: "fine to skip it for now, we'll
  pick it up eventually", then "skip check-doc-length for the ticket-3 commit".

## Scope (options to decide)
1. Exempt generated cards from the doc-length ratchet, because they are machine output.
2. Change the generator so cards stay within limits, for example by summarising or capping AC
   lists, or by linking to the AC store instead of listing every entry.

## Out of Scope
- The line-ending and link-resolution fixes, done in TICKET-20261002-WorktreeBootstrapLeavesTrackedFilesDirty.

## Comments
