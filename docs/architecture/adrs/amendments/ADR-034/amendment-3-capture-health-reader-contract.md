---
title: "ADR-034 Amendment 3 — The capture-health report reads attempts, gives four verdicts, and fails closed"
description: "Full text of Amendment 3 (2026-10-23) to ADR-034. It is part of ADR-034, not a separate ADR. The capture-health report counts capture attempts, not agent runs, gives one of four verdicts per period, refuses to give any verdict when it cannot locate the ledger, and reads only the telemetry stream, never the harvester or the emission sink."
type: "adr"
status: "active"
created: "2026-10-23"
last_updated: "2026-10-23"
deciders:
  - BrainCandy
components:
  - infrastructure
  - knowledge_system
  - agent_telemetry
related_docs:
  - docs/architecture/adrs/ADR-034-knowledge-write-ownership.md
  - docs/architecture/adrs/amendments/ADR-034/amendment-1-emission-goes-through-one-helper.md
  - docs/architecture/adrs/amendments/ADR-034/amendment-2-capture-attempt-ledger-is-telemetry.md
  - docs/architecture/adrs/ADR-011-learning-emission-sink.md
  - docs/architecture/adrs/ADR-069-durable-log-root-for-workspaces.md
  - docs/architecture/components/agent-telemetry.md
  - docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700b-3.yaml
  - docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700b-1-i.yaml
  - docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700b-1-ii.yaml
  - docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700a.yaml
related_code:
  - scripts/knowledge/health/capture_health_report.py
  - scripts/knowledge/sink_resolution.py
  - scripts/build_phases_knowledge.py
  - templates/skills/agent-telemetry/scripts/emit_event.py
---

# ADR-034 Amendment 3 — 2026-10-23 — The capture-health report reads attempts, gives four verdicts, and fails closed

> This is the full text of an amendment to
> [ADR-034: Knowledge Write Ownership](../../ADR-034-knowledge-write-ownership.md). It is part
> of ADR-034, not a separate ADR, and has no ADR number of its own. It sets the contract for
> the one reader of the capture-attempt ledger that
> [Amendment 2](amendment-2-capture-attempt-ledger-is-telemetry.md) created, and it departs
> from one sentence of Amendment 2 on purpose (A3.4).

| Field | Value |
|---|---|
| Amends | Adds A3.1–A3.7. Departs from Amendment 2's Operational sentence "An install with no usable declaration writes no ledger at all, so its periods fall in case 3, which is correct" for the reader only (A3.4). Extends Amendment 2's three cases to four (A3.2). A2.1–A2.8 otherwise stand. |
| Status | Accepted (BrainCandy took every decision it records on 2026-10-23) |
| Date | 2026-10-23 |
| Deciders | BrainCandy (attempts as the unit, four verdicts, fail closed, the stated A2.4 limit with no cross-check, all 2026-10-23). The defaults in A3.7 were taken on the architect's recommendation and are open to revision by BrainCandy. |
| Driven by | `INF-700b-3` ([AC](../../../../acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700b-3.yaml)), ticket `06_TICKET-20261016-INF-700b-3` in `EPIC-ALearningAnAgentHasTodayActuallyGets`, after architect-review on 2026-10-23 |
| Supersedes this ADR? | No. Option B stays confirmed, the harvester stays the sole writer to knowledge surfaces, and Amendments 1 and 2 stand except where A3.4 says otherwise. |

## Context

Amendment 2 made every run that reaches the capture step leave a `capture_attempt` record
on the operational telemetry stream, written only by `emit_event.py`, with outcome
`recorded`, `nothing-to-record` or `failed` and a `missing_target` key. `INF-700b-3` is the
reader: a report that tells a person, for a period, which kind of quiet it was. The AC asks
for counts of agent runs and three cases. Architect review on 2026-10-23 found that the
ledger cannot support that wording as written, and that the reader makes decisions no
earlier amendment covers:

- **There is no run id.** `emit_knowledge.py` writes one `recorded` attempt per learning
  (A2.4), so a run that records two learnings writes two records. Ticketless v3 agents carry
  a null ticket path (A2.6), so runs cannot be rebuilt from (agent, ticket) either. A count
  of runs cannot be derived.
- **Three cases are not a partition.** "None recorded and none failed", "any failed" and "no
  attempts" leave a period with `recorded >= 1` and `failed = 0` undefined. That is the
  healthy case: 7 of the 15 attempts on the live stream are `recorded`.
- **A reader that cannot find the ledger cannot tell that from a quiet period.** Amendment 2
  says an install with no usable declaration writes no ledger and so reads as case 3. For a
  writer that is right. For a reader it is a false all-clear: a dead ledger and a week in
  which no run reached the step would print the same answer.
- **Two counters must not meet.** `INF-700a` reports a routing backlog from the emission sink
  and the harvester's watermark. Its counters (`skipped_unknown`, `unroutable_by_kind`,
  `write_failures`, `state_persist_failed` in `scripts/knowledge/harvest_learnings.py`)
  describe routing, not capture. On 2026-08-26 every record on disk was unroutable while
  capture was merely silent, and a period of 5 failed attempts and a period of 5 recorded
  and harvested attempts both give a backlog of 0. Identical backlogs, opposite health.
- **The stream is shared and dirty.** It holds probe lines, `agent_start` events, legacy
  `knowledge_captured` lines, and one `capture_attempt` from before A2.2 with no
  `missing_target` key. The ticket's historic fixture also has truncated and non-object
  JSON. A report that crashes on one bad line reports nothing.

## Decision

**A3.1 — The unit counted is the capture attempt.**
The report MUST count `capture_attempt` records, one per record, and MUST label the figures
as attempts. It MUST NOT label them agent runs or derive a run count. For every period,
`attempts == recorded + nothing_to_record + failed`, and all four numbers MUST be printed,
including zeros. The AC's "agent runs" is read as attempts; the AC YAML is not edited by
this amendment.

**A3.2 — Four verdicts, decided by data, in a fixed order.**
Each period MUST get exactly one verdict, decided in this order:

1. No `capture_attempt` record in the period: `no-run-reached-the-step`.
2. Else any attempt with outcome `failed`: `capture-path-broken`.
3. Else any attempt with outcome `recorded`: `learnings-recorded`.
4. Else (every attempt is `nothing-to-record`): `nothing-to-record`.

The four strings MUST be pairwise different, so the verdict alone tells the cases apart
without opening a template or a source file. For `capture-path-broken` the report MUST name
each distinct `payload.missing_target` of the period's `failed` attempts, not just count
them. A `failed` attempt whose `missing_target` is null, empty or absent MUST be shown as
`(not recorded)`, never omitted. This extends Amendment 2's three cases with
`learnings-recorded`; Amendment 2's case 1 is this verdict, and its cases 2 and 3 are
verdicts 4 and 1.

**A3.3 — Periods come from the records' own timestamps; bad lines are counted, never fatal.**

- The period MUST be the half-open window `[since, until)`, chosen by each record's own
  `timestamp`, never by file position or by when the report runs, so a period re-reported
  later gives the same numbers.
- A naive `--since`, `--until` or record timestamp MUST be read as UTC. A date-only
  argument MUST mean midnight UTC of that date.
- A `capture_attempt` record whose timestamp is absent or not parseable ISO-8601, or whose
  outcome is outside the closed set of A2.2, MUST be counted as malformed and excluded from
  every period. It MUST NOT be dropped silently or attributed to the current period.
- A line that is not a JSON object, an object with no `event_type`, and any event type
  other than `capture_attempt` (probes, `agent_start`, legacy `knowledge_captured`) MUST be
  counted as unrecognised and skipped.
- A `capture_attempt` with no `payload.missing_target` key MUST still count as an attempt.
  The key MUST be read with a default, because records written before A2.2 lack it.
- The malformed and unrecognised counts MUST be printed separately from every period
  figure. A malformed or unrecognised line MUST NOT make the report exit with an error.

**A3.4 — The report fails closed when it cannot locate the ledger.**
*(BrainCandy's decision, 2026-10-23. A deliberate departure from Amendment 2.)*
The report MUST locate the stream by importing `read_usable_stream` and
`enduring_root_exists` from the sibling deployed `scripts/knowledge/sink_resolution.py`. It
MUST NOT copy the usable-stream rule (A2.7, `INF-500d-4-ix`). A `--stream PATH` option MUST
override the declaration, for tests and manual use.

- With no `--stream`, when the declaration is absent or unusable, or its enduring root is
  gone, the report MUST exit non-zero, name the declaration and the reason on stderr, and
  print no verdict on stdout.
- When the declaration is usable and the stream file does not exist yet, the report MUST
  give `no-run-reached-the-step`. A fresh install with a live root has simply not written yet.
- When the stream path exists but cannot be read (for example, a directory in its place),
  the report MUST exit non-zero and print no verdict.

Amendment 2's Operational section says an install with no usable declaration "writes no
ledger at all, so its periods fall in case 3, which is correct". That remains true of the
writers. It MUST NOT be true of the reader: the report MUST NOT produce
`no-run-reached-the-step`, or any verdict, from a ledger it could not find. This is the one
place where the report must not give its own all-clear.

**A3.5 — The report reads only the telemetry stream.**
The report lives at `scripts/knowledge/health/capture_health_report.py` and MUST be stdlib-only
apart from the `sink_resolution` import.

- It MUST read only the operational telemetry stream. It MUST NOT import anything from
  `scripts/knowledge/harvest_learnings.py`, MUST NOT read the knowledge-emission sink or the
  harvest watermark, and MUST NOT print a backlog figure or any harvester counter name.
  This is the reader-side twin of A2.1, which forbids the harvester to read the ledger: the
  dependency is absent in both directions.
- It MUST expose a pure `build_report(lines, since, until)` and a `main(argv)` CLI taking
  `--since`, `--until` and `--stream`. The `knowledge-harvester` agent MUST NOT call it.
- It MUST be deployed by naming it in both hand-kept lists in
  `scripts/build_phases_knowledge.py`: `deploy_scripts` in `build_knowledge_scripts` and the
  tuple in `_manifest_knowledge_scripts`.

**A3.6 — The report prints its two limits, and does not cross-check.**
The report MUST print, once per run, the two limits that bound what a verdict means:

- **A2.6.** A `failed` attempt can only exist where telemetry was still writable. A failure
  that also broke the telemetry writer leaves no record.
- **A2.4.** When the knowledge record is written but the `emit_event.py` subprocess cannot
  run, no `recorded` attempt exists. Such a period can read as `nothing-to-record`, or as
  `no-run-reached-the-step` when it was the only attempt.

*(BrainCandy's decision, 2026-10-23.)* The report MUST NOT cross-check the ledger against the
knowledge-emission sink to catch the A2.4 case. The limit is stated, not repaired.

**A3.7 — Defaults taken.**
*(Taken on the architect's recommendation, 2026-10-23. They are binding as written and open
to revision by BrainCandy.)*

- The report MUST carry no backlog section. `INF-700a` stays the backlog surface. A reader
  who needs both runs both; no combined number or section is built.
- The window rules of A3.3 (half-open, naive as UTC, date-only as midnight UTC) are defaults
  of this kind.
- The `(not recorded)` text of A3.2 for a `failed` attempt with no target is a default of
  this kind.

## Consequences

**Positive.** A person can read a period's health from one command, without a template or
the source: a broken path names what was missing, a quiet period is told apart from one in
which nothing ran, and a healthy period has a verdict of its own. A dead ledger can no
longer pass for a quiet week. The capture and routing counters cannot be summed, equated or
mistaken for each other, because the report never sees the routing side. Periods are
re-reportable, and one bad line cannot hide a whole stream. The usable-stream rule gains no
new copy.

**Negative.** The report departs from its own AC's wording twice: it counts attempts, not
runs, and it has four cases, not three. A reader of the AC alone will expect runs. A run
that records several learnings weighs more than one that records one, so attempt counts are
not a measure of how many agents did the step. The A2.4 undercount is stated, not closed: a
period whose only signal was a lost `recorded` attempt reads as quiet, and only stderr from
the original run shows why. An install with no usable declaration gets no report at all,
only an error, until it is rebuilt with a root. The deploy lists in
`scripts/build_phases_knowledge.py` are hand-kept, so forgetting one leaves the script out of
consumer installs.

**Operational.** The report must be tested as a subprocess, against a stream fixture or a
copied deployed layout with a re-declared stream; the source tree has no declaration, so a
source-tree run passes `--stream`. No test may read the live telemetry stream, which other
sessions append to. The real-artifact test freezes a fixture shaped like the live stream plus
the historic garbage, and must not hard-code its counts. `INF-700b-5` documents where the
report lives and how to read it; skill and agent wiring are out of scope here.

## Alternatives

- **Count agent runs, as the AC says.** Rejected by BrainCandy on 2026-10-23. The ledger has
  no run id, one run writes one `recorded` attempt per learning (A2.4), and ticketless v3
  agents have a null ticket path (A2.6), so a run count would be a guess presented as data.
- **Keep three verdicts and fold `learnings-recorded` into `nothing-to-record`.** Rejected.
  The healthy case would print as "agents had nothing to record", which is false whenever a
  learning was captured.
- **Report an unlocatable ledger as `no-run-reached-the-step`, as A2.6 implies.** Rejected by
  BrainCandy on 2026-10-23. A dead ledger and a period in which nothing ran would print the
  same verdict, which is the false all-clear this epic exists to close.
- **Cross-check the ledger against the knowledge-emission sink.** Rejected by BrainCandy on
  2026-10-23, as Amendment 2 already rejected it. It makes the report read the routing side,
  couples two counters with different denominators, and repairs one undercount by reading a
  stream whose records are not attempts.
- **Show the `INF-700a` backlog in the same report.** Rejected for this ticket (A3.7). The
  original test would have printed `backlog=0` beside `failed=5`, forcing the report to
  compute a routing-side number, and the two figures have different inputs and units.
- **Read the harvester's counters.** Rejected. They describe routing, and would label a
  healthy but unroutable capture as broken.
- **Copy the usable-stream rule into the report.** Rejected. It adds a copy that
  `INF-500d-4-ix`'s parity check would have to cover (A2.7). The report imports
  `sink_resolution` instead.
- **Abort on a malformed or unrecognised line.** Rejected. The stream is shared and already
  holds such lines, so a strict reader would report nothing on the real stream.
