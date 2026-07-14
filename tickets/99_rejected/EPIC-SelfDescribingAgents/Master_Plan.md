# EPIC: Self-Describing Agents (INF-600)

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
