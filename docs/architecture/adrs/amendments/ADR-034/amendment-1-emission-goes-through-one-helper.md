---
title: "ADR-034 Amendment 1 — Emission goes through one helper, and unclassified is a defined non-value"
description: "Full text of Amendment 1 (2026-10-17, revised 2026-10-20) to ADR-034. It is part of ADR-034, not a separate ADR. Agents emit only through the one deployed helper emit_knowledge.py, which reaches the sink through ADR-069's declaration, records the unclassified sentinel unrouted, and fails open without creating anything."
type: "adr"
status: "active"
created: "2026-10-17"
last_updated: "2026-10-21"
deciders:
  - BrainCandy
components:
  - infrastructure
  - knowledge_system
related_docs:
  - docs/architecture/adrs/ADR-034-knowledge-write-ownership.md
  - docs/architecture/adrs/amendments/ADR-034/amendment-2-capture-attempt-ledger-is-telemetry.md
  - docs/architecture/adrs/ADR-069-durable-log-root-for-workspaces.md
  - docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700b-1.yaml
related_code:
  - scripts/knowledge/emit_knowledge.py
  - scripts/knowledge/sink_resolution.py
  - scripts/ci/check_sink_parity.py
  - config/entry_kind_vocabulary.json
---

# ADR-034 Amendment 1 — 2026-10-17 — Emission goes through one helper, and unclassified is a defined non-value

> This is the full text of an amendment to
> [ADR-034: Knowledge Write Ownership](../../ADR-034-knowledge-write-ownership.md). It is part
> of ADR-034, not a separate ADR, and has no ADR number of its own. It was moved out of the
> ADR file unchanged on 2026-10-21 to keep that file within the doc-length limit.

| Field | Value |
|---|---|
| Amends | Decision item 1 (how the agent emits) and two sentences in "Consequences that follow mechanically" (the sink-path literal; the unrouted kind "never retried") |
| Status | Accepted |
| Date | 2026-10-17 (revised 2026-10-20 after review — see "Revision of 2026-10-20" below) |
| Deciders | BrainCandy (the sentinel decision and the choice to amend rather than write a new ADR, both 2026-10-17) |
| Driven by | `INF-700b-1` ([AC](../../../../acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700b-1.yaml)), ticket `01_TICKET-20261016-INF-700b-1` in `EPIC-ALearningAnAgentHasTodayActuallyGets`, after architect-review on 2026-10-16 |
| Supersedes this ADR? | No. Option B stays confirmed, Option A stays rejected, the harvester stays the sole writer. |

## Context

The decision above settled *who* writes. It left *how an agent emits* to the templates,
and the templates got it wrong in a way that keeps the loop open. `signoff` §7 step 2 and
the S9 blocks of `product-owner`, `business-analyst` and `it-po` say "Append the event
there (create the file if it does not exist yet)" and name no tool. None of these agents
has a safe append primitive:

- `Write` replaces the whole file, so it destroys every earlier emission.
- `Edit` needs a unique anchor, and an append-only JSONL file has none.
- Shell `>>` and `echo` are blocked by the file-mutation hook.

So an agent that follows the step literally cannot reliably produce one clean JSONL line.
A stray `</content>` line once found in the sink came from this. The INF-700b-1 clauses
"a durable record exists" and "the warning branch is not taken" therefore depended on
agent initiative.

A helper already existed. `scripts/knowledge/emit_knowledge.py` (INF-400c-5) appends a
validated `knowledge_captured` event and is deployed to `.leafcutter/scripts/knowledge/`,
but no emit site called it. It had three defects that blocked pointing §7 at it:

1. `--sink` was required, so every caller would restate a sink path in a template.
2. The documented sentinel `entry_kind: "unclassified"` is not a member of
   `config/entry_kind_vocabulary.json`, so the helper would reject it and write nothing.
   Every agent that cannot classify would then land on the warning branch again.
3. It called `mkdir(parents=True)`, which recreates a vanished project's log directory.
   [ADR-069](../../ADR-069-durable-log-root-for-workspaces.md#implementation-record-2026-10-12)
   forbids that.

Since this ADR was written, the sink question it called unsettled has been settled by
ADR-069: one durable `operational_log_root`, recorded at build time in
`.leafcutter/config/knowledge_sink.json`, with `knowledge_emission_sink` directly under it.

## Decision

**A1.1 — Agents emit through one deployed helper and never hand-append.**
Agents MUST still only emit. The harvester (`harvest_learnings.py`) MUST remain the sole
writer to knowledge surfaces. Emission MUST go through `scripts/knowledge/emit_knowledge.py`,
run from its deployed location. The capture step, meaning `signoff` §7 and the S9 blocks of
the three v3 agents, MUST call it with one identical invocation. A template MUST NOT instruct
an agent to append, create or write the sink itself. The record-shape JSON block stays in §7 as
the description of what the helper writes. A second emitter MUST NOT be added.
`templates/skills/agent-telemetry/scripts/emit_event.py` is not the knowledge emitter.
*(Scoped 2026-10-21 by [Amendment 2](amendment-2-capture-attempt-ledger-is-telemetry.md)
A2.2: this sentence and the ban on a second emitter apply to knowledge records. `emit_event.py`
is the sole writer of capture-attempt records, which are telemetry, not knowledge.)*

The invocation MUST pass the learning to `--text` in single quotes, with every embedded `'`
written as `'\''`, so the shell cannot expand a backtick, `$(...)`, `$VAR` or `"` inside it.
The helper then records the learning exactly as the agent wrote it. Double quotes MUST NOT
be used, because the shell expands them before the helper runs. *(Revised 2026-10-20 after
review.)*

**A1.2 — The helper reaches the sink only through ADR-069's declaration.**
When no `--sink` is given, the helper MUST default to the `knowledge_emission_sink` declared
under ADR-069's one durable log root. It MUST read that declaration through
`scripts/knowledge/sink_resolution.py`, applying ADR-069's usable-stream rule and then its
stale-root rule. It MUST NOT use a path literal, and it MUST NOT fall back to a relative
`debugging/logs/...` path. A template MUST NOT name a sink path. An explicit `--sink` keeps
working for tests and manual use. Its behaviour is set out in A1.4.

The helper MUST also offer a read-only `emit_knowledge.py --print-sink` flag. *(Added
2026-10-20 after review.)* It prints the absolute path of the sink the helper would write to
when called with no `--sink`. When the declaration is absent, unusable or stale, it prints
nothing on stdout, names the reason on stderr and exits non-zero. In every case it creates
nothing: no file and no directory. `scripts/ci/check_sink_parity.py` MUST recognise this flag
as a third resolution mechanism, beside `harvest_learnings.py --print-sink` and a literal
`debugging/logs/*.jsonl` path. The checker uses it to verify that each capture surface, meaning
`signoff` §7 and the three S9 blocks, reaches the declared sink. A surface that restates a
`--sink` path of its own does not reach the declared sink, and the checker reports it.

**A1.3 — `unclassified` is a defined non-value, recorded and left unrouted.**
*(BrainCandy's decision, 2026-10-17.)* A learning the agent cannot classify MUST be emitted
with the sentinel `entry_kind: "unclassified"`. The templates (`signoff` §7 and the three S9
blocks) MUST tell the agent to pass the pair `--entry-kind unclassified --destination
"(unrouted)"`. The helper enforces only the `entry_kind`. *(Revised 2026-10-20 after review:
the original text implied the helper enforced the pair. It does not.)* When `entry_kind` is
exactly `unclassified`, the helper records the event as given, with any `destination`, without
a vocabulary-membership check and without writing a rejection. The `(unrouted)` destination is
a template instruction, not a helper check. The harvester MUST leave such a record unrouted,
unmarked and counted `outstanding`, so a later run can route it. Every other out-of-vocabulary
kind keeps the helper's existing rejection behaviour.

The `entry_kind` vocabulary in `config/entry_kind_vocabulary.json`, owned by INF-400c-5,
MUST NOT change. `unclassified` is not a member and MUST NOT become one: it is a defined
non-value, not a destination.

**A1.4 — For the declared sink: fail open, create nothing above the log directory.**
*(Revised 2026-10-20 after review.)* This rule applies only to the declared sink, which the
helper uses when no `--sink` is given. When the declaration is absent, unusable (the stream is
not directly under an absolute `operational_log_root`) or stale (the enduring root is gone),
the helper MUST create nothing at all. It MUST print a warning to stderr naming the reason and
exit 0. This matches ADR-069, where every writer refuses a vanished project rather than
recreating it.

When the enduring root is live but the log directory is missing, the helper MAY create the
log directory. In the `<project>/debugging/logs` layout it MAY also create the `debugging/`
level between the project and the log directory. It MUST NOT recreate the enduring root
itself. It checks that the root is live before it creates any directory.

An explicit `--sink` or `--rejection-log` path supplied by the caller is honoured as given,
parent directories included, with no declaration or stale-root check. Choosing an explicit
path is the orchestrator's decision. ADR-069 governs the declared root, not paths a caller
passes in. A rejection log is written only when `--rejection-log` is given, so the declared
sink never gets a rejection-log file next to it.

A warning or non-zero exit from the helper MUST NOT block the agent's output or sign-off.

*Revision of 2026-10-20.* pr-reviewer found that the 2026-10-17 text of A1.4 disagreed with
the helper as built. It said the fail-open rule "applies to the `--rejection-log` path" and
that only "the log directory alone and nothing above it" is created. The code honours explicit
paths as given and creates the `debugging/` level in the `<project>/debugging/logs` layout.
The text above now states what the code does. The same review added the single-quote rule to
A1.1, the `--print-sink` flag to A1.2, and the pair-versus-enforcement distinction to A1.3.
The decision itself is unchanged.

## Consequences

**Positive.** An agent that follows the capture step literally produces one valid JSONL
line in the declared sink, because `json.dumps` escapes the newlines in `text`. The INF-700b-1
clauses no longer rest on agent initiative. Templates carry no sink path, so moving the log
root needs a rebuild and not a template edit. An agent that cannot classify still leaves a
durable record instead of taking the warning branch. The vocabulary owner is not pre-empted.

**Negative.** All four emission surfaces change together. `product-owner`, `business-analyst`
and `it-po` are high-traffic prompts, and a surface that lags leaves a mixed contract until
the parity tests catch it. Records with `entry_kind: "unclassified"` will collect in the sink
and stay `outstanding` until a classifier exists. That backlog is deliberate, but it is real.
The helper now owns one rule (the sentinel exemption) that the vocabulary file does not
show, so a reader of the vocabulary alone will not learn that `unclassified` is accepted.

**Operational.** The helper's behaviour depends on a deployed declaration, so it must be
verified against a built layout, not the source tree. A source-tree run has no declaration
and correctly refuses. A `--no-log-root` build records an empty declaration, and the helper
then warns and creates nothing on every call. That is the intended fail-open. It also means
such an install captures no learnings until it is rebuilt with a root.

## Alternatives

- **Keep the hand-append instruction.** Rejected. No agent has a primitive that appends one
  line safely (`Write` overwrites, `Edit` needs an anchor, `>>` is hook-blocked), so a
  literal-instruction agent either corrupts the sink or takes the warning branch.
- **Add `unclassified` to `config/entry_kind_vocabulary.json`.** Rejected by BrainCandy on
  2026-10-17. The vocabulary belongs to INF-400c-5 and lists destinations. Admitting a
  non-value would tell the harvester that `unclassified` is somewhere to route to.
- **Let the helper reject `unclassified`, so the agent must classify.** Rejected. No
  classifier exists inline: `route-learning` is retired, and `route-knowledge`'s taxonomy
  does not match the harvester's kinds (Decision, "Consequences that follow mechanically").
  Rejection would make the warning branch the only reachable path again.
- **Default to `resolve_default_sink()` and its relative `debugging/logs/knowledge_emissions.jsonl`.**
  Rejected. That is a path literal resolved against the current directory. In a per-drive
  worktree it writes to a log directory deleted with the worktree, which is the loss
  ADR-069 exists to prevent.
- **Use `agent-telemetry`'s `emit_event.py`.** Rejected. It writes a fixed telemetry record
  with no `text` field to the telemetry stream, not to the knowledge-emission sink.
  *(Still rejected as the knowledge emitter. [Amendment 2](amendment-2-capture-attempt-ledger-is-telemetry.md)
  A2.2 makes it the capture-attempt writer, which is a different record on a different
  stream.)*
- **Record this as a new ADR.** Rejected by BrainCandy on 2026-10-17. It refines how this
  ADR's emit obligation is carried out and does not compete with it. A separate record would
  leave readers to reconcile two ADRs on the same question.
