---
title: "ADR-034: Knowledge Write Ownership — the Harvester Writes, Agents Only Emit"
description: "Resolves three contradictory answers to who persists a captured learning by confirming ADR-011's deferred-harvest model as authoritative, demoting inline agent-side capture from deferred to rejected, and retiring the route-learning and capture-learning skill names. Amended 2026-10-17: agents emit only through the one deployed helper emit_knowledge.py, which reaches the sink through ADR-069's declaration, records the unclassified sentinel, and fails open without creating anything. Amended 2026-10-21: the capture-attempt ledger is telemetry written only by emit_event.py, and the helper writes the recorded attempt itself so a skipped second command cannot read as nothing to record."
type: "adr"
status: "active"
created: "2026-08-25"
last_updated: "2026-10-21"
deciders:
  - BrainCandy
components:
  - infrastructure
  - knowledge_system
related_docs:
  - docs/architecture/adrs/amendments/ADR-034/amendment-1-emission-goes-through-one-helper.md
  - docs/architecture/adrs/amendments/ADR-034/amendment-2-capture-attempt-ledger-is-telemetry.md
  - docs/architecture/adrs/ADR-011-learning-emission-sink.md
  - docs/architecture/adrs/ADR-069-durable-log-root-for-workspaces.md
  - docs/architecture/agent_knowledge_system.md
  - docs/architecture/components/knowledge-system.md
  - docs/known-issues/build-pipeline.md
  - docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700b-1.yaml
  - docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700b-1-i.yaml
  - docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700b-3.yaml
related_code:
  - scripts/knowledge/harvest_learnings.py
  - scripts/knowledge/emit_knowledge.py
  - templates/skills/agent-telemetry/scripts/emit_event.py
  - templates/skills/agent-telemetry/SKILL.md
  - scripts/knowledge/sink_resolution.py
  - scripts/ci/check_sink_parity.py
  - config/entry_kind_vocabulary.json
  - templates/skills/signoff/SKILL.md
  - templates/agents/product-owner.md
  - templates/agents/business-analyst.md
  - templates/agents/it-po.md
  - templates/agents/knowledge-harvester.md
---

# ADR-034: Knowledge Write Ownership — the Harvester Writes, Agents Only Emit

## Status

| Field | Value |
|---|---|
| Status | Accepted, amended |
| Date | 2026-08-25 |
| Amended | 2026-10-17 — Amendment 1 (emission goes through one helper; `unclassified` is a defined non-value), revised 2026-10-20 after review. See [Amendment 1](amendments/ADR-034/amendment-1-emission-goes-through-one-helper.md). 2026-10-21 — Amendment 2 (the capture-attempt ledger is telemetry, written by `emit_event.py`; the helper writes `recorded` itself), revised 2026-10-21 after review. See [Amendment 2](amendments/ADR-034/amendment-2-capture-attempt-ledger-is-telemetry.md). |
| Deciders | BrainCandy |
| Author | Written during the INF-400 consultation of 2026-08-25 (product-owner + business-analyst review) |
| Context ADRs | ADR-011 (learning emission sink) — this ADR resolves an ambiguity it left open; ADR-069 (durable log root) — Amendment 1 reaches the sink through its declaration |

> **Read the Decision section together with [Amendment 1](amendments/ADR-034/amendment-1-emission-goes-through-one-helper.md).**
> The ownership decision is unchanged: agents emit, the harvester writes. Amendment 1
> fixes *how* an agent emits, and two sentences in "Consequences that follow mechanically"
> (a sink-path literal and an unrouted kind being "never retried") no longer hold. Both are
> annotated in place; the original wording is kept.
>
> **[Amendment 2](amendments/ADR-034/amendment-2-capture-attempt-ledger-is-telemetry.md)
> adds a capture-attempt ledger.** It is telemetry, not knowledge, and `emit_event.py` is its
> only writer. Amendment 1's two statements that `emit_event.py` is not the emitter still hold
> for knowledge records; both are annotated in place.

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
   surface. *(Amended 2026-10-17: the append is performed by running
   `scripts/knowledge/emit_knowledge.py`, never composed by hand. See
   [Amendment 1](amendments/ADR-034/amendment-1-emission-goes-through-one-helper.md) §A1.1.)*
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
  `debugging/logs/knowledge_emissions.jsonl` — four places. *(Amended 2026-10-17: no
  template names a sink path. The four places name the helper, and the helper resolves
  the sink from ADR-069's declaration. See [Amendment 1](amendments/ADR-034/amendment-1-emission-goes-through-one-helper.md) §A1.2.)*
- `route-knowledge`'s 16-value `target_surface` taxonomy and the harvester's 11-value
  `_KNOWN_ENTRY_KINDS` overlap on only four values. An unrecognised kind is logged, **marked
  processed, and never retried** — so a naive repoint would silently discard 12 of 16
  routing outcomes. A vocabulary reconciliation is a prerequisite of any repoint, not a
  follow-up to it. *(Amended 2026-10-17: since INF-400c-2-ii the harvester leaves an
  unrecognised kind unmarked and counts it `outstanding`, so it is retried on a later run,
  not discarded. The prerequisite stands for any repoint of `route-knowledge`. See
  [Amendment 1](amendments/ADR-034/amendment-1-emission-goes-through-one-helper.md) §A1.3.)*
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

## Amendment 1 — 2026-10-17 — Emission goes through one helper, and unclassified is a defined non-value

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-17, revised 2026-10-20 after review |
| Amends | Decision item 1 and two sentences in "Consequences that follow mechanically" |
| Full text | [amendments/ADR-034/amendment-1-emission-goes-through-one-helper.md](amendments/ADR-034/amendment-1-emission-goes-through-one-helper.md) |

Agents MUST emit only by running the deployed `scripts/knowledge/emit_knowledge.py`, never
by hand-appending (A1.1). The helper reaches the sink only through ADR-069's declaration and
offers a read-only `--print-sink` (A1.2). `unclassified` is a recorded, unrouted non-value,
not a vocabulary member (A1.3). For the declared sink the helper fails open and creates
nothing above the log directory (A1.4).

## Amendment 2 — 2026-10-21 — The capture-attempt ledger is telemetry, written by one writer

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-21, revised 2026-10-21 after review |
| Amends | Adds A2.1–A2.8; scopes A1.1 and one Amendment 1 Alternatives bullet without withdrawing them |
| Full text | [amendments/ADR-034/amendment-2-capture-attempt-ledger-is-telemetry.md](amendments/ADR-034/amendment-2-capture-attempt-ledger-is-telemetry.md) |

A capture-attempt record is telemetry, never knowledge, and `emit_event.py` is its sole writer,
with a closed outcome set and `missing_target` on every record (A2.1–A2.2). The no-learning path
is one `emit_event.py` command (A2.3). `emit_knowledge.py` writes `recorded` (or `failed` on a
failed append) itself and refuses empty or metadata-only text (A2.4–A2.5); A2.6–A2.7 state limits.
Capture-step telemetry commands live once in named `agent-telemetry` sections that `signoff`
points to, and an agent records `failed` only on a non-zero helper exit, naming the script (A2.8).

## 5. References

- [ADR-011: Learning Emission Sink](ADR-011-learning-emission-sink.md) — chose the separate
  sink and left inline capture "deferred"; this ADR closes that opening.
- [ADR-069: One Durable Log Root for Every Workspace](ADR-069-durable-log-root-for-workspaces.md)
  — the declaration and usable-stream rule Amendment 1's helper reads the sink through.
- `scripts/knowledge/emit_knowledge.py` and `scripts/knowledge/sink_resolution.py` — the
  helper Amendment 1 makes the only emission path, and the resolver it reads.
- `templates/skills/agent-telemetry/scripts/emit_event.py` and
  `templates/skills/agent-telemetry/SKILL.md` — the sole capture-attempt ledger writer under
  Amendment 2, and the document that describes its record shape.
- `INF-700b-1-i` ([AC](../../acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700b-1-i.yaml))
  — drove Amendment 2. `INF-700b-1-ii` specifies the agent-run `failed` attempt.
  `INF-700b-3` ([AC](../../acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700b-3.yaml))
  reads the ledger.
- `INF-400c-4-iii` (the two-stream split and the same-keys-on-every-line rule) and
  `INF-500d-4-ix` (the usable-stream copy-parity check) — the constraints Amendment 2 keeps.
- [Knowledge System component](../components/knowledge-system.md) — the component this ADR
  governs.
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
