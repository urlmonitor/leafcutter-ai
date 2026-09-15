---
title: "KI-KM-009 — ADR-034 says the knowledge loop \"has never closed\"; nine files on disk say otherwise, and work was specified against the wrong premise"
description: "KI-KM-009 — ADR-034 says the knowledge loop \"has never closed\"; nine files on disk say otherwise, and work was specified against the wrong premise"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - knowledge_management
related_docs:
  - docs/known-issues/knowledge-management.md
  - docs/known-issues/README.md
---

# KI-KM-009 — ADR-034 says the knowledge loop "has never closed"; nine files on disk say otherwise, and work was specified against the wrong premise

> One known issue, split out of `docs/known-issues/knowledge-management.md` on
> 2026-09-14. Index: [knowledge-management.md](../knowledge-management.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26
- **Where:** `docs/architecture/adrs/ADR-034-knowledge-write-ownership.md` §1 (closing
  sentence) and §2 item 2

**Symptom.** ADR-034 §1 ends "So the loop has never closed, in any direction, in any
install." §2 then demotes inline agent-side capture (its Option A) from *deferred* to
**rejected**, and that demotion rests on the §1 finding.

The sentence is false. Resolving all 10 distinct `destination` paths named by the 28
`knowledge_captured` events in `debugging/logs/agent_telemetry.jsonl` finds **9 of 10
present in the repo**, sized 3608–23474 bytes and full of substantive content. The
busiest, `memory/feedback_itpo_agent_assignment_by_surface.md` (23 KB, the target of 10
events), opens "Captured 2026-06-16 during BO-210 / GE-102 technical enrichment" —
matching the timestamp, `agent` and `destination` of the first event exactly. `git log`
shows them committed during normal work in June 2026.

So the loop *did* close, informally: agents wrote the learning themselves and then emitted
a receipt. Inline capture is not merely an unrejected alternative — it is the **only**
mechanism that has ever produced knowledge in this repository. The harvester has never
written a single line.

**Why it matters beyond the wording.** Two ACs were specified on the strength of the false
premise, both proposing to *recover* the 28 events into knowledge surfaces. Because the
event schema carries no learning body (see `KI-KM-010`), executing either would have
appended 28 placeholder strings of the form `[agent-assignment-pattern] Learning from ` on
top of nine curated files that already hold the real content. Both are now withdrawn —
`INF-400c-5-ii` (`superseded_by: [INF-700c]`) and `INF-400c-4-ii`
(`superseded_by: [INF-700c-2]`) — but they reached `reviewed` readiness first.

**The honest reading is narrower than "Option A wins."** Inline capture is the only
mechanism that has produced anything, but partly because the harvester was never wired,
not because deferred harvest cannot work. What the evidence does establish is that the
write must hang off something that actually runs, and today the agent's own run is the
only such thing.

**Fix direction.** Correct §1's closing sentence and re-examine §2 item 2 against the
corrected premise. ADR-034 §6 already contains the trigger: review criterion 1, "a caller
for the harvester proves impractical, making deferred capture unreachable in practice
rather than merely unwired." Two months with one emission is evidence for that criterion.
Do not delete the ADR's history — amend with a dated correction, because the withdrawn ACs
cite it. The ADR carries `deciders: BrainCandy`; the §1 retraction is the author's to make,
not an agent's.

**Trap.** The 28 events look like a stranded backlog and invite a recovery ticket. Resolve
the `destination` paths **before** specifying any recovery: the interesting question is not
"can we route these?" but "is there anything in them to route, and is it already
somewhere?" Here the answer was no and yes respectively.

**Related.** `KI-KM-010` (the receipt-shaped schema). `KI-BP-007` (the dead
`route-learning` / `capture-learning` references that made the fail-open path the only
reachable one). `INF-700b`, `INF-700c` (the replacement features).

---
