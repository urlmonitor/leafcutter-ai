---
title: "ADR-011: Learning Emission Sink — Separate knowledge_emissions.jsonl vs Reuse agent_telemetry.jsonl"
type: "adr"
status: "active"
created: "2026-06-05"
last_updated: "2026-06-05"
deciders:
  - BrainCandy
components:
  - build_pipeline
related_docs:
  - docs/architecture/agent_knowledge_system.md
  - docs/architecture/adrs/ADR-001-self-hosting-boundary.md
  - tickets/00_inbox/epics/EPIC-AgentLearningLoop/01_harvester_agent_and_adr.md
related_code:
  - templates/skills/signoff/SKILL.md
  - scripts/knowledge/harvest_learnings.py
---

# ADR-011: Learning Emission Sink — Separate knowledge_emissions.jsonl vs Reuse agent_telemetry.jsonl

## Status

| Field | Value |
|---|---|
| Status | Active |
| Date | 2026-06-05 |
| Deciders | BrainCandy |
| Author | adr-author |
| Supersedes | — |

## Context

The `signoff` skill §7 (Knowledge Capture Step) instructs every phase agent to
emit a `knowledge_captured` event when it discovers something worth persisting:

```json
{
  "event": "knowledge_captured",
  "timestamp": "<ISO>",
  "ticket": "<ticket_path>",
  "destination": "<routed_file>",
  "entry_kind": "<entry_kind>"
}
```

This event is described in `agent_knowledge_system.md` §4 as going to
`agent_telemetry.jsonl`. However, `agent_telemetry.jsonl` is also the sink for
**all other agent operational events** — `agent_start`, `agent_signoff`,
`agent_retry`, `agent_failure`, `supervisor_dispatch`, `epic_complete`, etc.
These events are emitted by `ticket-supervisor` and `epic-supervisor` as
structural audit events with no semantic relationship to knowledge capture.

As of 2026-06-05, the worktree has only one JSONL sink under `debugging/logs/`:
`feedback.jsonl` (phase-agent sign-off feedback via `submit_feedback.py`).
The `agent_telemetry.jsonl` file is referenced in skill documentation but has
not yet been created as a committed artefact. This ADR records the decision made
before the harvester is implemented.

**Volume projections:**

- `knowledge_captured` events: expected to be sparse — typically 0–3 per ticket,
  arising only when a phase agent answers "yes" to the knowledge-capture prompt.
  Across an epic of 10 tickets with 9 phase agents each, this is at most ~270
  events, but empirically likely 10–30 events (most answers are "no").

- Operational telemetry (`agent_start`, `agent_signoff`, etc.): 3–6 events per
  phase agent invocation, so 270–540 events per 10-ticket epic. High-frequency,
  low-information events compared to knowledge events.

**Harvester requirements:**

The harvester (`harvest_learnings.py`) must:
1. Read unprocessed `knowledge_captured` events from the sink.
2. Invoke the `capture-learning` write protocol for each event.
3. Mark processed events so they are not replayed on the next run.
4. Produce a summary count by `entry_kind`.

The harvester's filtering task differs depending on the chosen sink:

- If reusing `agent_telemetry.jsonl`: the harvester must filter by
  `event == "knowledge_captured"` to ignore the high-volume operational noise.
- If using a dedicated `knowledge_emissions.jsonl`: the harvester can treat every
  line as a knowledge event and skip event-type filtering entirely.

**Replay semantics:**

The harvester must be idempotent — running twice with no new events should write
nothing. This requires tracking which events have been processed. Two approaches:

- **Offset file**: record the byte offset (or line count) up to which the sink has
  been consumed. Replay-safe only if the JSONL file is strictly append-only and
  never compacted or rotated.
- **Event hash set**: hash each event's unique key fields (ticket + timestamp + destination),
  store seen hashes, skip duplicates. Replay-safe regardless of file compaction.

The offset approach is simpler but fragile under sink rotation. The hash approach
is more robust at a small CPU cost. The harvester will use event hashes.

**Backward compatibility:**

Existing consumers of `agent_telemetry.jsonl` (retrospective-agent, feedback-analyst)
read operational events only. They do not parse `knowledge_captured` events and
would silently skip them if they appeared in the shared sink — so reusing the
shared sink would not break existing consumers. However, it would add noise to
their input streams that they must explicitly ignore.

## Decision

**Use a dedicated `knowledge_emissions.jsonl` sink.**

Phase agents that emit `knowledge_captured` events MUST write to
`debugging/logs/knowledge_emissions.jsonl` rather than to `agent_telemetry.jsonl`.

The harvester (`harvest_learnings.py`) reads exclusively from
`debugging/logs/knowledge_emissions.jsonl`.

## Rationale

1. **Single-purpose files are easier to filter.** The harvester processes every
   line in `knowledge_emissions.jsonl` as a knowledge event. There is no event-type
   filter required. Adding event filtering to the harvester introduces a code path
   that must be tested and maintained even though it provides no additional value —
   the filter exists only to compensate for mixing unrelated concerns in the same file.

2. **Separation of concerns for existing consumers.** Retrospective-agent and
   feedback-analyst read `agent_telemetry.jsonl` for operational audit data. Adding
   knowledge events to that file would require all current and future consumers to
   skip `knowledge_captured` lines explicitly. This is an invisible coupling that
   silently degrades the consumer's input quality over time.

3. **Replay isolation.** The harvester's offset or hash tracking file is specific to
   `knowledge_emissions.jsonl`. If the harvester ever needs to reset (e.g. after a
   target file is deleted and the knowledge must be re-routed), it resets only the
   knowledge emissions cursor, without risking confusion with operational event
   positions in the shared sink.

4. **Volume mismatch.** Operational events are high-frequency (hundreds per epic run);
   knowledge events are low-frequency (tens per epic run). Co-locating them in one file
   creates a 10:1 or higher noise-to-signal ratio in the knowledge consumer's input.
   A dedicated file keeps the knowledge consumer's input clean and fast.

5. **No backward-compatibility break.** Because `agent_telemetry.jsonl` does not yet
   exist as a committed file in the worktree (only `feedback.jsonl` exists), there is
   no existing content to migrate. The decision is forward-looking: when operational
   telemetry is formalised in a future ADR, it will use `agent_telemetry.jsonl`; when
   knowledge emissions are formalised here, they use `knowledge_emissions.jsonl`. Both
   files will be created on first write.

## Consequences

### Positive

- **Harvester implementation is simpler.** No event-type filtering required; every
  line in `knowledge_emissions.jsonl` is a knowledge event.
- **Existing consumers of operational telemetry are unaffected.** They read from
  `agent_telemetry.jsonl` (once it is formalised); the knowledge sink is invisible
  to them.
- **Replay semantics are file-scoped.** The harvester's cursor is specific to
  `knowledge_emissions.jsonl`. Reset operations are safe and bounded.
- **Observability is improved.** An operator can inspect `knowledge_emissions.jsonl`
  to see exactly what learnings have been emitted, without operational noise.

### Negative

- **Two sink paths to maintain.** Phase agents must emit `knowledge_captured` to
  `knowledge_emissions.jsonl`, while other telemetry goes to `agent_telemetry.jsonl`.
  This is an additional convention agents must follow correctly.
- **File creation discipline required.** Both files are created on first write. The
  `debugging/logs/` directory must exist. The pre-drive checklist already requires
  a writability probe on this directory.

### Neutral

- The `signoff` skill §7 references `agent_telemetry.jsonl` in the emit line. This
  reference MUST be updated to `debugging/logs/knowledge_emissions.jsonl` for
  `knowledge_captured` events specifically. Other event types (non-knowledge) continue
  to use `agent_telemetry.jsonl` when that sink is formalised.
- The harvester uses event-hash-based idempotency (not file offsets), which is
  compatible with both append-only semantics and future file rotation policies.

## Alternatives

### Alternative A — Reuse agent_telemetry.jsonl

Write `knowledge_captured` events into `agent_telemetry.jsonl` alongside all other
operational events (`agent_start`, `agent_signoff`, `agent_retry`, etc.).

**Rejected.** The harvester must then filter by `event == "knowledge_captured"`,
introducing a code path that only compensates for mixing unrelated concerns. Existing
and future consumers of the shared sink inherit noise. Volume mismatch (10:1 operational
to knowledge) reduces signal-to-noise for the harvester. The separation of concerns
argument is strong: operational audit events and knowledge capture events serve different
consumers with different access patterns.

### Alternative B — Single unified knowledge_captured field in feedback.jsonl

Extend the existing `feedback.jsonl` schema to include knowledge events alongside
phase-agent sign-off feedback.

**Rejected.** `feedback.jsonl` is written by `submit_feedback.py` and consumed by
`feedback-analyst`. Its schema is fixed around feedback categories (`complete`,
`knowledge-gap`, `quality-concern`, etc.) and is not suitable for JSONL event routing.
Repurposing it would require schema changes to both the writer and all readers.

### Alternative C — In-memory only (no persisted sink)

Emit knowledge events only in-memory during a session; do not persist them to any file.
Have the phase agent immediately invoke `capture-learning` inline, skipping the
deferred-harvest pattern entirely.

**Deferred, not rejected.** Inline knowledge capture (no sink, no harvester) is simpler
for small volumes and trivially idempotent (the agent writes the learning immediately).
However, it does not support batch harvesting, replay, or the supervisor's audit trail.
The EPIC-AgentLearningLoop design requires the deferred-harvest pattern for observability
and for the future `route-knowledge` skill integration. In-memory-only is a valid future
simplification if the harvester proves unnecessary operationally.

## References

- [Agent Knowledge System](../agent_knowledge_system.md) — describes the knowledge
  pipeline: `route-learning`, `capture-learning`, and the mandatory §7 knowledge-capture
  trigger in `signoff`.
- [signoff SKILL.md §7](../../templates/skills/signoff/SKILL.md) — the mandatory
  knowledge-capture step that emits `knowledge_captured` events.
- [ADR-001: Self-Hosting Boundary](ADR-001-self-hosting-boundary.md) — establishes
  the config-driven path resolution convention that governs sink paths in this project.
- EPIC-AgentLearningLoop ticket 01 — the commissioning ticket for this ADR and the
  `harvest_learnings.py` script it covers.
