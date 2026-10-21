---
title: "ADR-034 Amendment 2 — The capture-attempt ledger is telemetry, written by one writer"
description: "Full text of Amendment 2 (2026-10-21, revised 2026-10-21) to ADR-034. It is part of ADR-034, not a separate ADR. The capture-attempt ledger is telemetry written only by emit_event.py, the no-learning path is one emit_event.py command, and the helper writes the recorded attempt itself and refuses empty or metadata-only text."
type: "adr"
status: "active"
created: "2026-10-21"
last_updated: "2026-10-21"
deciders:
  - BrainCandy
components:
  - infrastructure
  - knowledge_system
related_docs:
  - docs/architecture/adrs/ADR-034-knowledge-write-ownership.md
  - docs/architecture/adrs/amendments/ADR-034/amendment-1-emission-goes-through-one-helper.md
  - docs/architecture/adrs/ADR-011-learning-emission-sink.md
  - docs/architecture/adrs/ADR-069-durable-log-root-for-workspaces.md
  - docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700b-1-i.yaml
  - docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700b-3.yaml
related_code:
  - scripts/knowledge/emit_knowledge.py
  - templates/skills/agent-telemetry/scripts/emit_event.py
  - templates/skills/agent-telemetry/SKILL.md
---

# ADR-034 Amendment 2 — 2026-10-21 — The capture-attempt ledger is telemetry, written by one writer

> This is the full text of an amendment to
> [ADR-034: Knowledge Write Ownership](../../ADR-034-knowledge-write-ownership.md). It is part
> of ADR-034, not a separate ADR, and has no ADR number of its own. It was moved out of the
> ADR file unchanged on 2026-10-21 to keep that file within the doc-length limit. It scopes
> two statements in [Amendment 1](amendment-1-emission-goes-through-one-helper.md).

| Field | Value |
|---|---|
| Amends | Adds A2.1–A2.7. Scopes two statements in Amendment 1 without withdrawing them: A1.1's "`emit_event.py` is not the knowledge emitter" and the Alternatives bullet "Use `agent-telemetry`'s `emit_event.py`. Rejected." Both are annotated in place. |
| Status | Accepted |
| Date | 2026-10-21 (revised 2026-10-21 after review — see "Revision of 2026-10-21" below) |
| Deciders | BrainCandy (the helper writes the `recorded` attempt itself, 2026-10-21) |
| Driven by | `INF-700b-1-i` ([AC](../../../../acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700b-1-i.yaml)), ticket `02_TICKET-20261016-INF-700b-1-i` in `EPIC-ALearningAnAgentHasTodayActuallyGets`, after architect-review on 2026-10-20. The ledger is read by `INF-700b-3` ([AC](../../../../acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700b-3.yaml)). |
| Supersedes this ADR? | No. Option B stays confirmed, the harvester stays the sole writer to knowledge surfaces, and A1.1–A1.4 all stand. |

## Context

`INF-700b-1-i` says an agent that has nothing to record produces no knowledge record. On its
own, that makes silence ambiguous. `INF-700b-3` reports on a period and must tell three cases
apart:

1. Agents reached the capture step and recorded learnings.
2. Agents reached the capture step and had nothing to record.
3. No agent run reached the capture step at all.

With no artefact for a run that reached the step, cases 2 and 3 look the same, and a broken
dispatch reads as a quiet week. So each run that reaches the step needs a durable
capture-attempt record. That record carries no learning, so it must not be a knowledge record.

Two existing rules decide where it goes. [ADR-011](../../ADR-011-learning-emission-sink.md) and
`INF-400c-4-iii` keep the knowledge-emission sink apart from the operational telemetry stream.
A non-knowledge line in the sink breaks that split, and the harvester would read it. A1.1 of
this ADR forbids a second knowledge emitter and says `emit_event.py` is not the knowledge
emitter. That is correct, but read without scope it would forbid `signoff` §7 from telling an
agent to run `emit_event.py` at all.

Architect review on 2026-10-20 found two more gaps:

- **`recorded` depends on the agent.** If an agent writes `recorded` with a second command
  after the helper, an agent that records a learning but skips that command makes the period
  read as "nothing to record". That is a false all-clear for `INF-700b-3`, which is the defect
  this epic exists to close.
- **The helper accepts any text.** `scripts/knowledge/emit_knowledge.py` takes any `--text`,
  including an empty or whitespace-only one. The AC's "no record whose text is empty or
  restates the run's descriptive fields" is therefore unenforced.

## Decision

**A2.1 — The capture-attempt ledger is telemetry, not knowledge.**
A capture-attempt record MUST be written to the operational telemetry stream. It MUST NOT be
written to the knowledge-emission sink. It carries no learning and is never a knowledge
record, and the harvester MUST NOT read it. The ledger never touches the knowledge sink, so
the two-stream split of ADR-011 and `INF-400c-4-iii` holds.

**A2.2 — `emit_event.py` is the sole ledger writer.**
`templates/skills/agent-telemetry/scripts/emit_event.py` MUST be the only code that writes a
capture-attempt record. It writes it as a new event type, `capture_attempt`.

- For `--event capture_attempt`, `--outcome` MUST be one of the closed set `recorded`,
  `nothing-to-record`, `failed`. An unknown outcome MUST write nothing, print a warning on
  stderr and exit 0. Other event types keep accepting free-text outcomes, because existing
  callers use values such as `ok` and `blocked`.
- Every record `emit_event.py` writes, of any event type, MUST carry the key
  `missing_target`. It is null by default. This keeps the rule that every line on the stream
  has the same keys (`INF-400c-4-iii`).
- For `--event capture_attempt`, `--missing-target` MUST be given when the outcome is
  `failed`, and MUST NOT be given for any other outcome, so `missing_target` is null on every
  `recorded` and `nothing-to-record` record. A `failed` call without it, or a `recorded` or
  `nothing-to-record` call with it, takes the same refusal path as an unknown outcome: it
  writes nothing, prints a warning on stderr and exits 0. *(Revised 2026-10-21 after review:
  "null otherwise" added.)*

This scopes A1.1. `emit_event.py` is not the knowledge emitter, and A1.1's ban on a second
emitter applies to knowledge records. `emit_event.py` is the capture-attempt writer. The two
statements do not conflict, because they govern different records on different streams.

**A2.3 — The no-learning path is one `emit_event.py` command.**
When the agent has nothing to record, it MUST run exactly one command, with outcome
`nothing-to-record` and no `--log`:

```bash
python3 <deployed emit_event.py> --agent <agent> --event capture_attempt --phase knowledge-capture --outcome nothing-to-record [--ticket <ticket>]
```

On that path the agent MUST NOT run `emit_knowledge.py`, and no knowledge record is produced.
The command prints nothing on success and always exits 0, so the agent's primary output and
sign-off are unchanged. The command MUST be identical in `signoff` §7 and the three v3 S9
blocks except for `--agent` and the optional `--ticket`. No template names a stream path
(A1.2, ADR-069).

**A2.4 — The helper writes `recorded` itself.**
*(BrainCandy's decision, 2026-10-21.)* After a successful append to the knowledge sink,
`emit_knowledge.py` MUST write the `recorded` attempt. It does this by invoking the deployed
`emit_event.py` as a subprocess, with the path derived from the deployed layout and no
`--log`. This step fails open: if `emit_event.py` cannot run, the helper prints a warning on
stderr and still exits 0, and the knowledge record already written stands. The agent MUST NOT
write `recorded` itself. The agent-facing `emit_knowledge.py` invocation in A1.1 is unchanged.

When the append to the knowledge sink itself fails with an `OSError`, `emit_knowledge.py` MUST
print a stderr WARNING naming the sink and the error, MUST write one `failed` attempt through
`emit_event.py` with `missing_target` set to the sink path, and MUST still exit 0. It writes no
`recorded` attempt on that path. The sink path is the explicit `--sink` when one was given,
otherwise the declared sink. *(Revised 2026-10-21 after review: the failed-append path was
added. Before it, a failed append wrote no attempt and gave no reason.)*

The reason: if agent initiative wrote `recorded`, an agent that recorded a learning but skipped
the second command would make the period read as "nothing to record", a false all-clear for
`INF-700b-3`. Code that runs straight after the knowledge write closes that gap. Ownership stays
as it was: the helper is still the sole writer to the knowledge sink, and `emit_event.py` is
still the sole writer to the ledger. The helper triggers `emit_event.py`; it does not write the
ledger line itself.

**A2.5 — The helper refuses empty or metadata-only text.**
`emit_knowledge.py` MUST whitespace-normalise `--text`. It MUST refuse the text when it is
empty, or when it is empty once every occurrence of the record's own `agent`, `component`,
`destination`, `entry_kind` and `ticket` values, and every non-alphanumeric character, are
stripped. A refusal:

- appends nothing to the knowledge sink;
- gives the reason on stderr;
- exits 0;
- writes a `nothing-to-record` attempt through `emit_event.py`, as in A2.4.

A refusal is `nothing-to-record`, not `failed`, because the agent had no learning to give. The
emit path MUST NOT contain any default, fallback, placeholder or f-string substitution for
`text`. This is the emitter-side twin of the writer-side substitution `INF-700c-1` removes.

**A2.6 — The ledger has two stated limits.**

- **Shared declaration.** The telemetry stream and the knowledge sink are declared in the same
  `.leafcutter/config/knowledge_sink.json` (ADR-069). When that declaration is absent, unusable
  or stale, both writers refuse, and the failure stays on stderr only. No ledger record of it
  can be written. A `failed` record therefore covers only failures where telemetry is still
  writable: a missing script, a `ModuleNotFoundError`, a bad sink key, and a knowledge sink
  that cannot be appended to (A2.4, the one `failed` record the helper writes itself). When the
  declaration is unusable and no `--sink` is given, the helper never attempts the append and
  writes no attempt. When an explicit `--sink` append fails under an unusable declaration,
  `emit_event.py` refuses the `failed` record and the helper warns on stderr that the attempt
  was not recorded. *(Revised 2026-10-21 after review.)* The agent-run `failed`
  variant (`--outcome failed --missing-target '<path>'`) is specified by `INF-700b-1-ii`, not
  here.
- **Ticketless agents.** The v3 agents (`product-owner`, `business-analyst`, `it-po`) run
  outside any ticket. Their attempt records carry a null ticket path.

**A2.7 — No new copy of the usable-stream rule.**
The helper MUST trigger `emit_event.py` rather than resolve the telemetry stream itself. No new
copy of ADR-069's usable-stream rule is added, so `INF-500d-4-ix`'s copy-parity check is not
widened. `emit_event.py` keeps the inline copy it already has in `_declared_stream`.

*Revision of 2026-10-21.* pr-reviewer found two places where the first 2026-10-21 text was
looser than the architect note it came from. A2.2 required `missing_target` on `failed` but
did not say it must be null otherwise, and `emit_event.py` accepted it on any outcome. A2.4
said stderr shows why a `recorded` attempt is missing, but a failed sink append wrote no
attempt and printed nothing. The code was changed to refuse `--missing-target` on `recorded`
and `nothing-to-record`, and to warn and write one `failed` attempt when the sink append
fails. A2.2, A2.4 and A2.6 above, and the Negative consequence below, now state what the
code does. The decision itself is unchanged.

## Consequences

**Positive.** `INF-700b-3` can tell its three cases apart from artefacts, not from the absence
of them. `recorded` is written by code that runs straight after the knowledge write, so a
skipped agent command cannot produce a false all-clear. Each stream keeps exactly one writer.
A contentless knowledge record is refused where it would be made, which matches the writer-side
fix in `INF-700c-1`. The usable-stream rule gains no new copy.

**Negative.** `emit_knowledge.py` now depends on `agent-telemetry`'s `emit_event.py` being
deployed, a coupling across the `scripts/` and `templates/` boundary. If that subprocess
cannot run, the knowledge record exists but no `recorded` attempt does, and `INF-700b-3` will
undercount recorded runs for that period; only stderr shows why, because no ledger writer ran.
A failed append to the knowledge sink is different: it leaves a `failed` attempt naming the
sink (A2.4), so the ledger shows it. For that case, stderr alone shows why only when the shared
declaration is unusable, because `emit_event.py` then refuses the `failed` record too.
*(Revised 2026-10-21 after review.)* Every `emit_event.py` record
gains the `missing_target` key, so any reader or test that pins the exact payload key set
(`unit_tests/test_emit_event.py`) must be updated on purpose. The four capture surfaces change
together again. The refusal rule will also refuse a learning made only of the record's own
metadata words, even if an agent meant it as content. That is accepted: such a record tells a
later agent nothing it could not read from the record's other fields.

**Operational.** The helper-to-`emit_event.py` path must be verified as subprocesses against a
built layout, never by importing either script; the source tree has no declaration. An install
with no usable declaration writes no ledger at all, so its periods fall in case 3, which is
correct. The new no-learning wording in `signoff` §7 and the S9 blocks must not put the words
"emit" and `knowledge_captured` in one paragraph ahead of the existing helper paragraph:
`scripts/ci/check_sink_parity.py` takes the first such paragraph and would report the surface
unparseable.

## Alternatives

- **Write attempt records through `emit_knowledge.py` into the knowledge sink.** Rejected. It
  puts a non-knowledge line in the knowledge sink, which breaks the two-stream split of ADR-011
  and `INF-400c-4-iii`, and the harvester would read it.
- **Let the agent write `recorded` with a second command.** Rejected by BrainCandy on
  2026-10-21. An agent that records a learning but skips the second command makes the period
  read as "nothing to record", a false all-clear. Keeping it would also require `INF-700b-3`
  to cross-check the knowledge sink to catch that case.
- **Have the helper write the ledger line itself.** Rejected. It adds a second ledger writer
  and a new copy of ADR-069's usable-stream rule, which widens `INF-500d-4-ix`'s parity check.
- **Infer "nothing to record" from the absence of knowledge records.** Rejected. An absence
  cannot tell "reached the step, nothing to record" from "never reached the step".
- **Keep free-text outcomes for `capture_attempt`.** Rejected. `INF-700b-3` counts by outcome,
  so a misspelled outcome would silently drop the record from every count.
- **Add `missing_target` only to `failed` records.** Rejected. It breaks the rule that every
  line on the telemetry stream has the same keys (`INF-400c-4-iii`).
- **Record a refused text as `failed`.** Rejected. The agent had no learning to give, so
  `failed` would inflate the failure count with runs where nothing went wrong.
