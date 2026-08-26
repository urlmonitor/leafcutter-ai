---
title: "ADR-034: Knowledge Write Ownership — the Harvester Writes, Agents Only Emit"
description: "Resolves three contradictory answers to who persists a captured learning by confirming ADR-011's deferred-harvest model as authoritative, demoting inline agent-side capture from deferred to rejected, and retiring the route-learning and capture-learning skill names."
type: "adr"
status: "active"
created: "2026-08-25"
last_updated: "2026-08-25"
deciders:
  - BrainCandy
components:
  - infrastructure
  - knowledge_system
related_docs:
  - docs/architecture/adrs/ADR-011-learning-emission-sink.md
  - docs/architecture/agent_knowledge_system.md
  - docs/known-issues/build-pipeline.md
related_code:
  - scripts/knowledge/harvest_learnings.py
  - templates/skills/signoff/SKILL.md
  - templates/agents/knowledge-harvester.md
---

# ADR-034: Knowledge Write Ownership — the Harvester Writes, Agents Only Emit

## Status

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-08-25 |
| Deciders | BrainCandy |
| Author | Written during the INF-400 consultation of 2026-08-25 (product-owner + business-analyst review) |
| Context ADRs | ADR-011 (learning emission sink) — this ADR resolves an ambiguity it left open |

## 1. Context

A consumer reported that "those knowledge-capture skills aren't available." Investigation
found `route-learning` and `capture-learning` referenced by path in six shipped template
surfaces — `signoff/SKILL.md` §7, PO v3, BA v3, IT-PO v3, `retrospective-agent`, and
`templates/skills/README.md` — with no directory for either and no commit ever having
created one.

The deeper finding was not the missing files. **The repository contains three mutually
incompatible answers to a single question: who writes a captured learning to disk?**

| # | Owner | Where it is asserted |
|---|---|---|
| A | The agent, inline, via `capture-learning` | `INF-400b-1` item 3; `INF-400b-2` (`destination` is "the file path where the learning **was** persisted" — past tense); the S8/S9 blocks in PO v3, BA v3 and IT-PO v3 |
| B | The harvester, deferred | **ADR-011's Decision section**; `INF-400c-2`; `scripts/knowledge/harvest_learnings.py`; `templates/agents/knowledge-harvester.md` |
| C | The user, per item | `retrospective-agent.md` — the classifier labels, the user approves each write |

A and B **double-write** if both ever run. ADR-011 recorded inline capture as its
Alternative C and marked it *"Deferred, not rejected"* — so the architecture of record
chose B while the templates went on describing A. Both were authored on 2026-06-05 and
never reconciled.

Three consequences followed, all of them silent:

- **Every call site fails open.** `signoff` §7 declares the step "**mandatory** — skipping
  it is a protocol violation" and then adds "If `route-learning` or `capture-learning` are
  unavailable, log a warning and proceed." The escape hatch is therefore the only reachable
  path, in every install, since the feature shipped.
- **Emissions go to a sink nothing reads.** §7 and the three v3 agents emit
  `knowledge_captured` to `agent_telemetry.jsonl`; `harvest_learnings.py` reads
  `knowledge_emissions.jsonl`. ADR-011 §175-178 explicitly recorded that the §7 emit line
  had to be updated to the new sink. It never was. 28 `knowledge_captured` events have
  accumulated in the wrong file; the right file has never existed.
- **Nothing invokes the harvester.** `knowledge-harvester` appears nowhere outside its own
  template and the agent registry — no supervisor, workflow or command calls it.

So the loop has never closed, in any direction, in any install.

## 2. Decision

**ADR-011's deferred-harvest model is authoritative. Agents emit; the harvester writes.**

Concretely:

1. **Option B is confirmed.** A phase agent's only knowledge-capture obligation is to append
   one `knowledge_captured` event to the emission sink. It performs no write to a knowledge
   surface.
2. **Option A is rejected, not deferred.** ADR-011's Alternative C is hereby demoted from
   *"Deferred, not rejected"* to **rejected**. Inline agent-side capture is not a future
   option held in reserve; it is the losing design, and leaving it nominally alive is what
   allowed the templates to keep describing it for three months.
3. **`route-learning` and `capture-learning` are retired as concepts.** They are the
   vocabulary of Option A. They are not to be authored. Their references are to be struck
   from `signoff` §7, the four agent templates, and `templates/skills/README.md`.
4. **Option C stands, scoped to `retrospective-agent` only.** Its user-approval-per-item
   model is a deliberate difference, not drift: a retrospective proposes Knowledge Items for
   human approval and must not write unattended. It classifies with `route-knowledge` and
   writes nothing itself.
5. **`route-knowledge` is the classifier for all three paths.** It already exists, and its
   `allowed-tools: Read` frontmatter is correct and load-bearing — a classifier that cannot
   write cannot silently become a second writer.
6. **The file-format contract belongs to the harvester.** The header, section and ordering
   requirements in `INF-400d-1`, `d-2` and `d-3` are the writer's responsibility, and the
   writer is `harvest_learnings.py`. Its `_default_capture` currently appends bare text and
   does not implement them; that is a known gap, owned here rather than by a skill.

### Consequences that follow mechanically

These are entailed by the decision and are recorded so nobody re-derives them:

- The emit target in `signoff` §7 and the three v3 agents must change to
  `debugging/logs/knowledge_emissions.jsonl` — four places.
- `route-knowledge`'s 16-value `target_surface` taxonomy and the harvester's 11-value
  `_KNOWN_ENTRY_KINDS` overlap on only four values. An unrecognised kind is logged, **marked
  processed, and never retried** — so a naive repoint would silently discard 12 of 16
  routing outcomes. A vocabulary reconciliation is a prerequisite of any repoint, not a
  follow-up to it.
- The harvester needs a caller. Until it has one, it is manual-invoke, and that must be
  stated wherever it is documented rather than implied to be automatic.

## 3. Alternatives Considered

**Adopt Option A (inline capture).** Author `capture-learning` as a real skill, keep
`route-knowledge` as classifier, promote ADR-011's Alternative C. Rejected: it discards a
harvester that is already written, tested and deployed to every consumer, and it reinstates
the double-write hazard against ADR-011's own reasoning. It is also the more expensive path
for a strictly worse replay story — an inline write cannot be re-run against corrected
routing rules, and a sink can.

**Descope the loop entirely.** Delete the six dangling references, mark INF-400b/c/d
superseded, keep only the injection half. Rejected: it writes off working, shipped
infrastructure to avoid a wiring problem, and the L0 benefit — that the system gets better
the more a project uses it — remains one the project wants.

**Leave the contradiction and repoint the callers at `route-knowledge`.** Rejected on
evidence. It fixes the one link that was never broken (classification), leaves the sink
mismatch and the absent caller untouched, and converts a visible warning into a silent
green — `route-knowledge` returns a clean routing decision, writes nothing, and reports
success. Against a phase whose exit criterion is "no false all-clear", that makes the
reported symptom harder to see rather than fixing it.

## 4. Consequences

**Good.** One writer, named and already built. The double-write hazard is closed by
construction rather than by convention. Replay becomes possible: a corrected routing table
can be re-run over a retained sink, which no inline design permits. `route-knowledge`'s
read-only frontmatter is now a load-bearing guarantee rather than an accident.

**Bad.** `capture-learning` will never be authored, and the `retrospective-agent` path loses
the shared write executor it was written against — that agent's §KI flow needs its own
treatment under Option C. The v3 agents' S8/S9 blocks must be rewritten, and they are
high-traffic files. Until the harvester has a caller, capture is not automatic and any
documentation implying otherwise is wrong.

**Neutral but load-bearing.** This ADR does not itself change any template. It records the
decision so the reconciliation work can be planned against a settled answer instead of
re-litigating write ownership a fourth time.

## 5. References

- [ADR-011: Learning Emission Sink](ADR-011-learning-emission-sink.md) — chose the separate
  sink and left inline capture "deferred"; this ADR closes that opening.
- [Agent Knowledge System](../agent_knowledge_system.md) — describes the Option A pipeline;
  now superseded on the write step and needing amendment.
- `docs/known-issues/build-pipeline.md` → KI-BP-007 — the dangling-reference finding that
  started this.
- `INF-400b`, `INF-400c`, `INF-400d` — the acceptance criteria this decision governs.
  `INF-400b-1`, `b-1-i`, `b-1-ii`, `d-2` and `f-3` name the retired skills inside their
  Gherkin and require amendment or supersession.
- `BO-2000a-5` (build-orchestration) — asserts §7's presence in the shared sign-off block;
  changing §7's content touches another component's shipped AC.

## 6. Review Criteria

Revisit this decision if any of the following becomes true:

- A caller for the harvester proves impractical, making deferred capture unreachable in
  practice rather than merely unwired.
- Emission volume makes a retained sink expensive enough that replay stops paying for itself.
- A use case appears that genuinely requires the learning to be readable by the same agent
  run that produced it — the one capability an inline write has and a deferred harvest does
  not.
