---
title: "Knowledge harvester agent and emission sink ADR"
status: todo
components:
  - infrastructure
created: 2026-06-05
depends_on:
  - tickets/00_inbox/epics/EPIC-AgentLearningLoop/00_v3_template_knowledge_steps.md
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: true
files_touched:
  - docs/architecture/adrs/ADR-NNN-learning-emission-sink.md
  - scripts/knowledge/harvest_learnings.py
  - tests/knowledge/test_harvest_learnings.py
  - templates/agents/knowledge-harvester.md
agents:
  architect-review: needed
  adr-author: needed
  architecture-diagram-author: not_needed
  test-writer: needed
  python-coder: needed
  llm-expert: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
source_acs:
  - INF-400c-1
  - INF-400c-2
  - INF-400c-3
  - INF-400c-2-i
---

# 01: Knowledge harvester agent and emission sink ADR

## Actor / Goal

As the leafcutter-ai system, I want an ADR documenting the emission sink
decision and a harvester agent that reads learning emissions and routes
each to the correct knowledge surface — so that agent learnings end up
in the right places automatically.

## Context

Ticket 00 adds emission steps to the v3 agents. Those agents emit raw
`knowledge_captured` events to a JSONL sink. This ticket delivers two
things:

1. **The ADR**: decides whether to reuse `agent_telemetry.jsonl` or create
   a separate `knowledge_emissions.jsonl` sink. This decision must be made
   and documented BEFORE the harvester is implemented.

2. **The harvester**: a script (`harvest_learnings.py`) that reads unprocessed
   `knowledge_captured` events from the chosen sink, invokes the
   `capture-learning` write protocol for each, marks events as processed,
   and reports a summary.

## Acceptance Criteria

```gherkin
# AC-1: ADR documents emission sink decision (INF-400c-1)

Given the existing feedback infrastructure uses two JSONL sinks:
  - feedback.jsonl (phase-agent sign-off feedback),
  - agent_telemetry.jsonl (structured telemetry events),
When the system is designed for learning emission routing,
Then an ADR is authored at docs/architecture/adrs/ADR-NNN-learning-emission-sink.md
  that documents:
  1. The decision context (what learning emissions are, volume expectations),
  2. The options considered (reuse telemetry sink vs. separate sink vs. other),
  3. The chosen option with rationale,
  4. The consequences (impact on harvester, replay semantics, backward compatibility),
And the ADR is authored BEFORE any harvester implementation begins.

# AC-2: Harvester routes emissions to correct knowledge surfaces (INF-400c-2)

Given the emission sink contains three knowledge_captured events:
  - Event 1: entry_kind "memory-project", destination "memory/project_infra.md"
  - Event 2: entry_kind "per-folder-readme", destination
    "docs/acceptance-criteria/infrastructure/README.md"
  - Event 3: entry_kind "agent-frontmatter", destination
    ".claude/skills/signoff/PROJECT_CONTEXT.md"
When the harvester process runs,
Then it reads each unprocessed event from the sink,
And for each event, it writes the learning text to the file at the destination
  using the capture-learning write protocol,
And it marks each processed event so it is not re-processed on the next run,
And it produces a summary: "3 learnings routed: 1 memory, 1 readme, 1 project-context".

# AC-3: Harvester is idempotent (INF-400c-3)

Given the harvester has already processed 5 events from the sink,
When the harvester is run again with no new events,
Then no files are written or modified,
And the summary reports: "0 learnings routed (5 previously processed)".

# AC-4: Harvester skips unrecognized entry_kind (INF-400c-2-i)

Given the emission sink contains an event with entry_kind "unknown_surface",
When the harvester processes it,
Then it logs a warning naming the unrecognized entry_kind and event details,
And it marks the event as processed (so it is not retried on every run),
And it does not crash or stop processing subsequent events.
```

## Sign-offs

- [ ] architect-review
- [ ] adr-author
- [ ] test-writer
- [ ] python-coder
- [ ] llm-expert
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### architect-review

- [ ] Read existing telemetry infrastructure: `scripts/feedback/submit_feedback.py`,
  `debugging/logs/agent_telemetry.jsonl` structure, and any existing consumers
  of telemetry events.
- [ ] Evaluate the two sink options (reuse vs. separate) against: replay
  semantics, event filtering cost, backward compatibility with existing
  telemetry consumers, volume projections.
- [ ] Produce the ADR scope statement for `adr-author`.

### adr-author

- [ ] Author the ADR at `docs/architecture/adrs/ADR-NNN-learning-emission-sink.md`
  using the scope statement from architect-review.
- [ ] Follow existing ADR numbering convention.

### test-writer

- [ ] Write `tests/knowledge/test_harvest_learnings.py`:
  - `test_routes_memory_project_event`: fixture with one memory-project event;
    assert file written at destination.
  - `test_routes_per_folder_readme_event`: fixture with one readme event;
    assert file written at destination.
  - `test_idempotent_no_duplicates`: run twice with same events; assert
    second run writes nothing.
  - `test_skips_unrecognized_entry_kind`: fixture with unknown entry_kind;
    assert warning logged, no crash.
  - `test_empty_sink_no_op`: empty sink; assert no files written.

### python-coder

- [ ] Implement `scripts/knowledge/harvest_learnings.py`:
  - CLI: `--sink <path>` (default: from ADR), `--dry-run`, `--verbose`.
  - Read JSONL sink, filter for `event: "knowledge_captured"`.
  - Track processed events via offset file or event hash set.
  - For each unprocessed event: invoke capture-learning write protocol.
  - Summary output: count by entry_kind.
  - Error handling per project error handling policy.

### llm-expert

- [ ] Write `templates/agents/knowledge-harvester.md` agent template
  if the harvester should be an agent rather than a standalone script.
  Decision depends on ADR outcome.

## Risk & Safety

- Touches money? No.
- Touches data? Reads JSONL sink (read-only). Writes to knowledge surfaces
  (PROJECT_CONTEXT.md, README.md, memory files). All writes use the
  capture-learning protocol which is append-only.
- The ADR gates implementation: if the ADR is not authored, the harvester
  cannot be built.
