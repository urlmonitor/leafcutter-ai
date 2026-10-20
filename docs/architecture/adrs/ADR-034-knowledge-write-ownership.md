---
title: "ADR-034: Knowledge Write Ownership — the Harvester Writes, Agents Only Emit"
description: "Resolves three contradictory answers to who persists a captured learning by confirming ADR-011's deferred-harvest model as authoritative, demoting inline agent-side capture from deferred to rejected, and retiring the route-learning and capture-learning skill names. Amended 2026-10-17: agents emit only through the one deployed helper emit_knowledge.py, which reaches the sink through ADR-069's declaration, records the unclassified sentinel, and fails open without creating anything."
type: "adr"
status: "active"
created: "2026-08-25"
last_updated: "2026-10-20"
deciders:
  - BrainCandy
components:
  - infrastructure
  - knowledge_system
related_docs:
  - docs/architecture/adrs/ADR-011-learning-emission-sink.md
  - docs/architecture/adrs/ADR-069-durable-log-root-for-workspaces.md
  - docs/architecture/agent_knowledge_system.md
  - docs/architecture/components/knowledge-system.md
  - docs/known-issues/build-pipeline.md
  - docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700b-1.yaml
related_code:
  - scripts/knowledge/harvest_learnings.py
  - scripts/knowledge/emit_knowledge.py
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
| Amended | 2026-10-17 — Amendment 1 (emission goes through one helper; `unclassified` is a defined non-value), revised 2026-10-20 after review. See [Amendment 1](#amendment-1--2026-10-17--emission-goes-through-one-helper-and-unclassified-is-a-defined-non-value). |
| Deciders | BrainCandy |
| Author | Written during the INF-400 consultation of 2026-08-25 (product-owner + business-analyst review) |
| Context ADRs | ADR-011 (learning emission sink) — this ADR resolves an ambiguity it left open; ADR-069 (durable log root) — Amendment 1 reaches the sink through its declaration |

> **Read the Decision section together with [Amendment 1](#amendment-1--2026-10-17--emission-goes-through-one-helper-and-unclassified-is-a-defined-non-value).**
> The ownership decision is unchanged: agents emit, the harvester writes. Amendment 1
> fixes *how* an agent emits, and two sentences in "Consequences that follow mechanically"
> (a sink-path literal and an unrouted kind being "never retried") no longer hold. Both are
> annotated in place; the original wording is kept.

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
   [Amendment 1](#amendment-1--2026-10-17--emission-goes-through-one-helper-and-unclassified-is-a-defined-non-value) §A1.1.)*
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
  the sink from ADR-069's declaration. See [Amendment 1](#amendment-1--2026-10-17--emission-goes-through-one-helper-and-unclassified-is-a-defined-non-value) §A1.2.)*
- `route-knowledge`'s 16-value `target_surface` taxonomy and the harvester's 11-value
  `_KNOWN_ENTRY_KINDS` overlap on only four values. An unrecognised kind is logged, **marked
  processed, and never retried** — so a naive repoint would silently discard 12 of 16
  routing outcomes. A vocabulary reconciliation is a prerequisite of any repoint, not a
  follow-up to it. *(Amended 2026-10-17: since INF-400c-2-ii the harvester leaves an
  unrecognised kind unmarked and counts it `outstanding`, so it is retried on a later run,
  not discarded. The prerequisite stands for any repoint of `route-knowledge`. See
  [Amendment 1](#amendment-1--2026-10-17--emission-goes-through-one-helper-and-unclassified-is-a-defined-non-value) §A1.3.)*
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
| Amends | Decision item 1 (how the agent emits) and two sentences in "Consequences that follow mechanically" (the sink-path literal; the unrouted kind "never retried") |
| Status | Accepted |
| Date | 2026-10-17 (revised 2026-10-20 after review — see "Revision of 2026-10-20" below) |
| Deciders | BrainCandy (the sentinel decision and the choice to amend rather than write a new ADR, both 2026-10-17) |
| Driven by | `INF-700b-1` ([AC](../../acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700b-1.yaml)), ticket `01_TICKET-20261016-INF-700b-1` in `EPIC-ALearningAnAgentHasTodayActuallyGets`, after architect-review on 2026-10-16 |
| Supersedes this ADR? | No. Option B stays confirmed, Option A stays rejected, the harvester stays the sole writer. |

### Context

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
   [ADR-069](ADR-069-durable-log-root-for-workspaces.md#implementation-record-2026-10-12)
   forbids that.

Since this ADR was written, the sink question it called unsettled has been settled by
ADR-069: one durable `operational_log_root`, recorded at build time in
`.leafcutter/config/knowledge_sink.json`, with `knowledge_emission_sink` directly under it.

### Decision

**A1.1 — Agents emit through one deployed helper and never hand-append.**
Agents MUST still only emit. The harvester (`harvest_learnings.py`) MUST remain the sole
writer to knowledge surfaces. Emission MUST go through `scripts/knowledge/emit_knowledge.py`,
run from its deployed location. The capture step, meaning `signoff` §7 and the S9 blocks of
the three v3 agents, MUST call it with one identical invocation. A template MUST NOT instruct
an agent to append, create or write the sink itself. The record-shape JSON block stays in §7 as
the description of what the helper writes. A second emitter MUST NOT be added.
`templates/skills/agent-telemetry/scripts/emit_event.py` is not the knowledge emitter.

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

### Consequences

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

### Alternatives

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
- **Record this as a new ADR.** Rejected by BrainCandy on 2026-10-17. It refines how this
  ADR's emit obligation is carried out and does not compete with it. A separate record would
  leave readers to reconcile two ADRs on the same question.

## 5. References

- [ADR-011: Learning Emission Sink](ADR-011-learning-emission-sink.md) — chose the separate
  sink and left inline capture "deferred"; this ADR closes that opening.
- [ADR-069: One Durable Log Root for Every Workspace](ADR-069-durable-log-root-for-workspaces.md)
  — the declaration and usable-stream rule Amendment 1's helper reads the sink through.
- `scripts/knowledge/emit_knowledge.py` and `scripts/knowledge/sink_resolution.py` — the
  helper Amendment 1 makes the only emission path, and the resolver it reads.
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
