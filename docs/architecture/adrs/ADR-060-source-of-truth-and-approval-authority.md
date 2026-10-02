---
title: "ADR-060: Source of Truth and Approval Authority — Git Is Canonical, a Human Approves, Precedent Is Evidence"
description: "Git is canonical for declared knowledge and published decision records; run artifacts and traces are not. Only a human approval creates a decision record, no record can self-authorize, the kernel never writes the repository during a run, and precedent is evidence that a human must confirm before it settles anything."
type: "adr"
status: "active"
created: "2026-10-01"
last_updated: "2026-10-01"
deciders:
  - BrainCandy
components:
  - decision_kernel
related_docs:
  - docs/architecture/adrs/ADR-053-intelligence-selection-deterministic-jev-llm-human.md
  - docs/architecture/adrs/ADR-056-colony-memory-evidence-reinforcement.md
  - docs/architecture/adrs/ADR-059-decision-store-reviewable-yaml-records-now-graph-later.md
  - docs/architecture/adrs/ADR-061-identity-of-declared-and-learned-records.md
  - docs/architecture/components/decision-kernel.md
  - docs/analysis/2026-10-01-neo4j-colony-memory-concept-2-layers-truth-sync.md
  - docs/analysis/2026-10-01-colony-memory-stage0-delta-4-decisions-needed.md
  - tickets/00_inbox/TICKET-20261001-KernelDecisionStore.md
related_code:
  - kernel/memory/builder.py
  - kernel/memory/publish.py
  - kernel/memory/precedent.py
  - kernel/memory/models.py
---

# ADR-060: Source of Truth and Approval Authority — Git Is Canonical, a Human Approves, Precedent Is Evidence

## Status

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-01 |
| Deciders | BrainCandy |
| Author | Claude Code, recording the user's decisions in [TICKET-20261001-KernelDecisionStore](../../../tickets/00_inbox/TICKET-20261001-KernelDecisionStore.md) |
| Supersedes | None |

## Context

Three places hold facts about a decision: the repository, the run (its checkpoints, artifacts and
Langfuse trace) and, in the user's concept, a graph. The concept's source-of-truth rule is that
source-derived nodes are never edited in the graph and that learned knowledge "may initially live
only in Neo4j"
([concept part 2](../../analysis/2026-10-01-neo4j-colony-memory-concept-2-layers-truth-sync.md),
section 7). [ADR-059](ADR-059-decision-store-reviewable-yaml-records-now-graph-later.md) puts
learned decisions in Git instead. [ADR-053](ADR-053-intelligence-selection-deterministic-jev-llm-human.md)
gives preference and authority to a human, and
[ADR-056](ADR-056-colony-memory-evidence-reinforcement.md) section 3 rule 5 says evidence may
rank and propose but never legislate. A model-written record that later runs trust as authority
would be the failure all three guard against.

## Decision

### 1. Git is canonical for declared knowledge and published decision records

A published record in `docs/decisions/` is the canonical form of a decision. Run artifacts (staged
records, `run.json`, interaction packets, the checkpoint database) and Langfuse traces are
operational history and MUST NOT be treated as canonical. A graph backend, when one exists, is an
index over Git, not a second source.

### 2. Only a human approval creates a record

A record MUST be built only from a decision whose status is `resolved`, whose approval status is
`approved`, whose approver is a human actor (`human` or `human:<id>`) and which carries an approval
time. The record schema allows the single approval status `approved`. A decision approved by
Jev, a host or the kernel itself MUST NOT produce a record.

### 3. Records cannot self-authorize

The kernel MUST stay read-only toward the repository during a run: it stages an approved record in
the run's artifacts and nothing more. A record enters `docs/decisions/` only when a person runs
`python -m kernel decisions publish --run-id <run>` after validation, so the change goes through
normal git review. The `/leafcutter` skill MAY tell the user that a record is staged; it MUST NOT
run publish. Nothing in a record, and no precedent, MAY grant a permission.

### 4. Precedent is evidence, never authority

An earlier approved decision is offered to a new decision as `prior_decisions` evidence with its
approver and date. Jev judges whether it applies. A precedent MUST NOT resolve a decision without a
human confirmation, and MUST NOT change routing scores or thresholds (the calibration gate of
ADR-056 section 9 stands). When a precedent applies strongly the human is asked once, in plain
words, to reuse it or to decide anew.

### 5. Reuse is a fresh approval; corrections are explicit and append-only

Reusing a precedent is approved by the current human and is staged as its own record that cites
the precedent. If the human decides anew against a precedent, the new record notes it, and the
kernel does not edit the older record. A correction to a published record is written only by
`decisions publish --correct <old-id>`; it appends a correction entry (reason, time, approver,
preserved evidence and assumptions) and a `superseded_by` link, and changes nothing else.

## Consequences

### Positive

- No model output becomes authority by being filed or by being old.
- The approval trail is the git history of a record, plus its `approval` block.
- The repository is never written by a run, so a failed or hostile run cannot change it.

### Negative

- A staged record is lost if nobody publishes it before the run root is cleaned. The skill's notice
  and the run report name it.
- A person must run one command per run that produced a record.
- A reuse question interrupts a run; the threshold that triggers it is configuration
  (`memory.reuse_threshold`).

### Operational

- `kernel/memory/builder.py` is the single gate that refuses an unapproved decision;
  `kernel/memory/publish.py` is the only writer of `docs/decisions/`.

## Alternatives

- **Let the kernel write `docs/decisions/` at the end of a run.** Rejected: it writes model output
  into the repository without review and makes the run non-read-only.
- **Auto-reuse a precedent that scores high.** Rejected: that lets an old, possibly wrong
  decision settle a new one with no human, which ADR-053 and ADR-056 forbid.
- **Treat Langfuse or the graph as canonical.** Rejected: neither is reviewed, and a trace can be
  incomplete or degraded.

## References

- [ADR-059: Decision store](ADR-059-decision-store-reviewable-yaml-records-now-graph-later.md)
- [ADR-053: Intelligence selection](ADR-053-intelligence-selection-deterministic-jev-llm-human.md)
- [ADR-056: Colony memory](ADR-056-colony-memory-evidence-reinforcement.md)
- [Colony memory concept, part 2](../../analysis/2026-10-01-neo4j-colony-memory-concept-2-layers-truth-sync.md)
