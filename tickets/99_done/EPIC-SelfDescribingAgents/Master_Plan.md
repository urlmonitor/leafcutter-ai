---
title: "EPIC: Self-Describing Agents (INF-600)"
type: epic
status: done
change_target: pipeline
risk_surface: internal
components:
  - build_pipeline
created: 2026-06-05
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
---

# EPIC: Self-Describing Agents (INF-600)

> **Recovered 2026-08-18.** This plan was the sole occupant of
> `tickets/99_rejected/EPIC-SelfDescribingAgents/`, moved there by PR #275 as an
> "empty shell" — accurate as a description of the folder, which held no tickets,
> but the folder was not empty of *content*: `tickets/99_done/EPIC-SelfDescribingAgents/`
> has the five tickets and **no plan at all**, so this was the epic's only
> Master_Plan and deleting the folder would have destroyed it. Moved here instead.
>
> Frontmatter added in the same pass: the file had none, and the ticket
> frontmatter guard requires it. `status: done` reflects the verified state —
> `scripts/generate_agent_cards.py`, `scripts/registry_validator.py`, 63 cards
> under `docs/agents/cards/` and `test_agent_verification_consistency.py` are all
> live, and all five tickets are signed off.
>
> Recovered by branch `chore/epic-duplicate-repair`.

## Goal
Every agent describes itself completely enough that its full profile is assembled automatically — never hand-written, never stale.

## AC Coverage
- L0: INF-600 (Understand any agent without reading its source)
- L0: INF-900 (Find any agent's full profile in seconds)
- L1s: INF-600i, INF-600j, INF-600b, INF-600g, INF-600h

## Tickets (dependency order)

| # | Ticket | ACs Covered | Depends On |
|---|--------|-------------|------------|
| 01 | Schema definition prototype | INF-600i, INF-600j (L2s: a-1 through a-6) | — |
| 02 | Card generator | INF-600b | 01 |
| 03 | Agent categories | INF-600h | 02 |
| 04 | Build enforcement gate | INF-600g | 03 |
| 05 | Rollout to all agents | INF-600i, INF-600j (full coverage) | 04 |

## Success Criteria
- `python build.py` generates a complete agent card for every agent
- Cards match the quality of the manually-authored prototype at `docs/agents/cards/python-coder.card.md`
- Build fails if any agent is missing required self-description metadata
- All 40+ agents have populated structured fields

## Prototype Reference
- `docs/agents/cards/python-coder.card.md` — the golden reference for card format
- `docs/acceptance-criteria/infrastructure/INF-600-self-describing-agents/` — full AC tree
