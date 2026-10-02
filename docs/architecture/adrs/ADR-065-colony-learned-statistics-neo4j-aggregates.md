---
title: "ADR-065: Colony Learned Statistics Live in Neo4j as Derived Aggregates — Supersedes ADR-057 in Part"
description: "The colony memory store for learned statistics is Neo4j, not PostgreSQL. Statistics are precomputed aggregates that the application maintains in the graph after specific actions: derived, rebuildable, never canonical and never workflow state, reached through ADR-059's ColonyMemory port. One optional learning store instead of PostgreSQL beside a graph; ADR-057's optionality, hot-path, context, run-root and staging rules stay in force. Amendment 1 (2026-10-02): every added item that feeds an aggregate triggers a full rebuild, statistics use ADR-062's Neo4j settings from the project .env, an unavailable store is retried, and each client has its own store, superseding ADR-057 §8's shared colony memory."
type: "adr"
status: "active"
created: "2026-10-02"
last_updated: "2026-10-02"
deciders:
  - BrainCandy
components:
  - decision_kernel
  - colony_memory
related_docs:
  - docs/architecture/adrs/ADR-057-colony-memory-store-optional-postgres.md
  - docs/architecture/adrs/ADR-056-colony-memory-evidence-reinforcement.md
  - docs/architecture/adrs/ADR-058-langfuse-colony-history-scores-datasets.md
  - docs/architecture/adrs/ADR-059-decision-store-reviewable-yaml-records-now-graph-later.md
  - docs/architecture/adrs/ADR-060-source-of-truth-and-approval-authority.md
  - docs/architecture/adrs/ADR-061-identity-of-declared-and-learned-records.md
  - docs/architecture/components/colony-memory.md
  - docs/architecture/components/decision-kernel.md
  - docs/analysis/2026-10-01-colony-memory-stage0-delta-2-reuse-and-mvp.md
  - docs/analysis/2026-10-01-colony-memory-stage0-delta-3-lessons-adrs-ownership.md
  - docs/analysis/2026-10-01-colony-memory-stage0-delta-4-decisions-needed.md
related_code:
  - kernel/memory/port.py
  - kernel/memory/backend.py
---

# ADR-065: Colony Learned Statistics Live in Neo4j as Derived Aggregates — Supersedes ADR-057 in Part

## Status

| Field | Value |
|---|---|
| Status | Accepted, amended |
| Date | 2026-10-02 |
| Amended | 2026-10-02 — [Amendment 1](#amendment-1--2026-10-02--open-questions-answered-each-client-has-its-own-store): Open Questions 1, 3, 5 and 6 answered, 4 narrowed; ADR-057 §8 superseded. |
| Deciders | BrainCandy |
| Author | `adr-author`, recording BrainCandy's binding decision of 2026-10-02 |
| Supersedes | [ADR-057](ADR-057-colony-memory-store-optional-postgres.md) in part: §1's store technology, §2, the §3 PostgreSQL implementation, §4's `LEAFCUTTER_COLONY_DB_URL`, §6, and the PostgreSQL and Supabase side of its Alternatives; by Amendment 1, also §8 (shared colony memory). §5 below lists what stays in force. |

> **Read the Decision section together with
> [Amendment 1](#amendment-1--2026-10-02--open-questions-answered-each-client-has-its-own-store).**
> It records BrainCandy's answers of 2026-10-02: an added item that feeds an aggregate triggers a
> full rebuild, statistics use ADR-062's Neo4j and settings, an unavailable store is retried, and
> each client has its own store. There is no shared colony memory. ADR-057 §8 is superseded.

## Context

[ADR-057](ADR-057-colony-memory-store-optional-postgres.md) (2026-09-30) made the colony memory
store, the pheromone map of [ADR-056](ADR-056-colony-memory-evidence-reinforcement.md), an
optional plain-PostgreSQL database behind a `ColonyMemory` port. Its sibling
[ADR-058](ADR-058-langfuse-colony-history-scores-datasets.md) made Langfuse the colony history.
No code exists for the PostgreSQL store.

A day later, the Stage 0 review of the user's Neo4j colony memory concept planned a graph ADR
([delta, part 3](../../analysis/2026-10-01-colony-memory-stage0-delta-3-lessons-adrs-ownership.md),
ADR plan): "Colony memory store is a graph (Neo4j) behind `ColonyMemory`". It was to supersede
ADR-057 §1, §2, the §3 implementation list, the §4 variable names, §6 and the Postgres
Alternatives. The review asked two questions
([part 4](../../analysis/2026-10-01-colony-memory-stage0-delta-4-decisions-needed.md)):

- #1, supersede ADR-057 in part or amend it in place. Recommended: supersede in part, and land
  ADR-057 as written first.
- #2, Neo4j instead of PostgreSQL or alongside it. Recommended: instead.

Neither question was answered at the time, and the graph ADR was never written.

The number it had reserved went to
[ADR-059](ADR-059-decision-store-reviewable-yaml-records-now-graph-later.md) instead. On
2026-10-01 the user decided "no Neo4j yet" for decision records. Approved decisions are YAML files
in Git, reached through the `ColonyMemory` port in `kernel/memory/port.py` (`find_decisions`,
`get_decision`, `stage_decision`; `memory.backend` is `file` or `null`), and "a graph backend MUST
be able to replace the file backend without any change to the kernel". ADR-059 names ADR-057 but
does not amend it. [ADR-060](ADR-060-source-of-truth-and-approval-authority.md) makes Git
canonical for declared knowledge and published decision records.
[ADR-061](ADR-061-identity-of-declared-and-learned-records.md) keys records by
(repository_id, kind, id).

ADR-062 "Standalone Knowledge Retrieval over Immutable Git Projections" is on a feature branch and
not yet on main. It brings Neo4j in for knowledge retrieval over immutable generations of Git
projections, with separate ingestion and retrieval credentials. Its code defines the settings
`LEAFCUTTER_NEO4J_URI`, `LEAFCUTTER_NEO4J_USERNAME`, `LEAFCUTTER_NEO4J_PASSWORD`,
`LEAFCUTTER_NEO4J_DATABASE`, `LEAFCUTTER_NEO4J_WRITER_USERNAME` and
`LEAFCUTTER_NEO4J_WRITER_PASSWORD`. ADR-062 introduces no runtime decision or lesson store, states
that direct Neo4j writes do not become canonical memory, and does not touch ADR-057.

Left as it is, ADR-057 binds the first learned statistic to PostgreSQL while the repository plans
Neo4j for retrieval. That is two database technologies, each with its own setup, secrets and
migrations, for two optional features. The roadmap's COLLECT step (`phase_colony_1_collect`) would
start on a store the user no longer wants.

The user decided on 2026-10-02:

> "We should already have a neo4j ADR which supersedes the postgres. For statistics we can just
> use mat views in neo, which we update after specific actions."

The ADR the user remembered was planned but never written. This is that ADR. It answers the review's #1
with "supersede in part" (ADR-057 landed as written) and #2 with "instead". Neo4j has no native
materialized-view feature. This ADR therefore names the mechanism by what it does: aggregates
computed ahead of time and maintained by the application after specific actions.

The review made three further recommendations
([part 2](../../analysis/2026-10-01-colony-memory-stage0-delta-2-reuse-and-mvp.md), Mode 0;
part 4, decision 4):

- Use `NullColonyMemory` when no `LEAFCUTTER_NEO4J_URI` is set or the opt-out is set. This is
  ADR-057 §4's rule with the new settings, and §4 below carries it over.
- Let a configured but unreachable store behave like Mode 0 for that run, with one warning and a
  run limitation. This stayed a recommendation (Open Question 5). Amendment 1 (A1.4) answers it
  with retry.
- Keep statistics derived, rebuildable from Langfuse and run records, and never workflow state.
  The user's words cover this: statistics that are updated after actions are derived (§2).

## Decision

### 1. The learned-statistics store is Neo4j, not PostgreSQL

- The colony memory store that holds learned statistics, the pheromone map of ADR-057 §1, MUST be
  a Neo4j database. Leafcutter MUST NOT add a PostgreSQL store for learned statistics.
- The store keeps its name and its role. ADR-057 §1's split still holds: "Langfuse remembers what
  happened. The colony memory store remembers what Leafcutter learned."
- The Neo4j driver and its version pin are left to the build. Hosting is open (Open Question 7).

### 2. Statistics are derived aggregates, maintained after specific actions

- Learned statistics MUST be stored in the graph as precomputed aggregates: values computed from
  run outcomes ahead of time and kept as nodes or properties that the application maintains.
  Neo4j has no native materialized views. "Materialized view" here names this pattern, not a
  database feature.
- The application MUST update the affected aggregates after specific actions. Routing MUST read
  the stored aggregates and MUST NOT compute statistics from raw records at read time.
- Amendment 1 settles which actions trigger an update (A1.1) and that each trigger runs a full
  rebuild (A1.2). The aggregate model is open (Open Question 2).
- Aggregates MUST be rebuildable from the records they are derived from: Langfuse traces and
  scores, and the run records the learning evaluator reads (ADR-057 §5). Losing the store MUST NOT
  lose canonical data.
- Aggregates MUST NOT be treated as canonical. ADR-060 §1 stands: Git is canonical for declared
  knowledge and published decision records, and a graph backend is not a second source.
- Aggregates MUST NOT be workflow state. The V0 run root and its checkpoints stay authoritative for
  a run (ADR-057 §9). The kernel MUST NOT checkpoint to the store or resume from it.

### 3. One port: the Neo4j backend attaches to ADR-059's `ColonyMemory`

- All access to learned statistics MUST go through the `ColonyMemory` port that ADR-059 defines in
  `kernel/memory/port.py`. The Neo4j backend MUST attach to that port. A second memory port MUST
  NOT be introduced.
- The implementation MUST be chosen once, at startup. Code outside that choice MUST NOT branch on
  whether Neo4j is configured (ADR-057 §3, carried over). `NullColonyMemory` stays the
  implementation that remembers nothing.
- The names and signatures of the statistics operations on the port are left to the build.
  ADR-057 §3's method list stays illustrative.
- This ADR does not move decision records. They stay YAML files in Git (ADR-059 §1, ADR-060), so
  the port serves records from files and statistics from the graph. How the startup choice
  composes the two backends is left to the build.

### 4. Configuration: the Neo4j settings replace `LEAFCUTTER_COLONY_DB_URL`

- Leafcutter MUST NOT read `LEAFCUTTER_COLONY_DB_URL` (ADR-057 §4). The `LEAFCUTTER_NEO4J_*`
  settings that ADR-062 introduces, listed in Context, replace it. The statistics use the same
  Neo4j and the same settings as ADR-062 (Amendment 1, A1.3).
- `LEAFCUTTER_SELF_LEARNING=false` stays the explicit opt-out (ADR-057 §4).
- The statistics store stays optional. Without a configured Neo4j store, or with the opt-out set,
  learned statistics MUST be off: nothing is recorded and no statistics are read. This MUST NOT
  switch off decision records. Precedent from day one (ADR-059 §5) follows ADR-059's
  `memory.backend` setting (`file` by default) whether or not Neo4j is configured, so
  `NullColonyMemory` is selected only when `memory.backend` is `null`. The kernel, Jev, LangGraph,
  the Claude Code handoff and Langfuse tracing MUST keep working without the statistics store
  (ADR-057 §3 and §4, carried over).

### 5. What stays in force from ADR-057 and ADR-058

| ADR-057 | After this ADR |
|---|---|
| §1 The store is the pheromone map | In force, except the store technology (§1 here) |
| §2 Plain PostgreSQL, reached by a connection URL | Superseded by §1 here |
| §3 One `ColonyMemory` port, chosen once at startup | In force: optional, Null implementation, chosen once. Superseded: the PostgreSQL implementation. The port is ADR-059's (§3 here) |
| §4 Configuration | Superseded: `LEAFCUTTER_COLONY_DB_URL` (§4 here). In force: the `LEAFCUTTER_SELF_LEARNING=false` opt-out |
| §5 The hot path reads the store, never Langfuse | In force. The store it reads is Neo4j |
| §6 Conventional relational tables | Superseded by §2 here |
| §7 Mandatory context dimensions | In force. Their encoding in the graph is part of Open Question 2 |
| §8 Shared colony memory | Superseded by Amendment 1 (A1.5): each client has its own store, and there is no shared colony memory |
| §9 The run root stays authoritative | In force |
| §10 Staged adoption and its gates | In force |
| Alternatives | Superseded: the PostgreSQL and Supabase side. Still rejected: Langfuse as the live store, SQLite or local files only, a mandatory store, a custom tracing backend. The SQLite rejection's ADR-057 reason (no sharing, §8) fell with Amendment 1; it stays rejected because the store is Neo4j (§1 here) |
| Open Questions | 1 and 6 were restated here as Open Questions 6 and 5, and Amendment 1 closes both. The others stay open and now apply to the Neo4j store. For 4, Amendment 1 (A1.1) settles when the aggregates are updated; placement stays open |

ADR-058 is unchanged, except that its three-layer table (§6) now points at Neo4j through this ADR.

### 6. "No Neo4j yet" stands for decision records; statistics start with COLLECT

- ADR-059's "no Neo4j yet" (2026-10-01) concerned decision records, and it stands. This ADR MUST
  NOT be read as moving decision records into Neo4j.
- Learned statistics MUST start only with the roadmap's COLLECT step (`phase_colony_1_collect`,
  ADR-057 §10). This ADR does not change kernel V0 scope.

## Consequences

### Positive

- One optional learning store technology. Retrieval (ADR-062) and learned statistics use the same
  database technology, so an adopter who turns both on sets up, secures and upgrades one kind of
  store, not two.
- Routing reads precomputed values. Aggregation is paid for when a trigger action happens, not on
  every routing decision, and routing stays independent of Langfuse (ADR-057 §5).
- Statistics are derived and rebuildable. Losing or resetting the store loses no canonical
  knowledge, and a change to the aggregate model can be handled by a rebuild.
- The kernel keeps one memory port. A Neo4j backend attaches without a kernel change, and
  Leafcutter still runs with no store at all.
- No PostgreSQL store was built, so nothing has to be migrated.

### Negative

- Neo4j has no native materialized views, so Leafcutter's own code maintains the aggregates. A
  missed or failed update leaves an aggregate stale until the next update or rebuild, and every
  new trigger action has to update the right aggregates.
- Counters and rates are aggregation work, which is not a graph database's primary strength. The
  review's revisit condition applies: if Stage 4 statistics prove too heavy for the graph, a new
  ADR reopens the choice.
- A Neo4j server is more to provide than a PostgreSQL connection URL. ADR-057's convenience of
  pasting any Postgres or Supabase connection string is gone, and hosting is open (Open
  Question 7).
- The configuration rests on settings that ADR-062 introduces, and ADR-062 is not yet on main.
  Until it lands, those names have no code on main.
- The port serves two kinds of data from two backends: decision records from files and statistics
  from the graph. Two startup inputs meet: ADR-059's `memory.backend` and the Neo4j settings with
  the opt-out.
- Carried from ADR-057: full learning still needs Langfuse, the store and an evaluator between
  them. Learning is off by default, so early statistics are sparse and noisy, and a database
  driver joins the kernel's dependencies. ADR-057's shared-store privacy cost no longer applies,
  because there is no shared store (Amendment 1, A1.5).

### Operational

- `.env` no longer uses `LEAFCUTTER_COLONY_DB_URL`. The Neo4j settings are credentials under the
  existing secrets convention (ADR-057, Operational): never logged, reported only as present or
  absent, and redacted before telemetry export. `LEAFCUTTER_SELF_LEARNING=false` keeps learning
  off.
- Review rejects:
  - a second memory port;
  - a branch on the Neo4j configuration outside the startup choice;
  - a statistic recorded without ADR-057 §7's minimum context dimensions;
  - a statistic that the kernel treats as canonical or as workflow state;
  - a statistic written into Git.
- ADR-056, ADR-057 and ADR-058 now point to this ADR. The component docs, the vision, the roadmap
  and the glossary are updated separately.
- Kernel V0 scope is unchanged. No statistics code is built before COLLECT.

## Alternatives

- **Keep PostgreSQL (ADR-057 as written).** Rejected: BrainCandy's 2026-10-02 decision supersedes
  it. ADR-057's Alternatives never weighed a graph database. With Neo4j planned for knowledge
  retrieval (ADR-062), a PostgreSQL store would be a second database technology for an optional
  feature.
- **PostgreSQL for counters, Neo4j for the graph** (the review's part 4, decision 2, option b).
  Rejected. Two stores double the setup, the secrets and the migrations for every adopter who
  turns learning on.
- **Compute statistics on demand from Langfuse.** Rejected. Every routing decision would wait on a
  remote query over raw traces, and routing would depend on a service that is allowed to be
  unavailable. ADR-057 §5 and ADR-056 §8 forbid the hot path to query Langfuse.
- **YAML files for statistics.** Rejected. Counters would churn Git after every trigger action,
  and the kernel stays read-only toward the repository during a run (ADR-060 §3). ADR-059 keeps
  files for human-approved records only, and statistics are not canonical (§2).

## Open Questions

This ADR explicitly did not decide the questions below. Amendment 1 answers 1, 3, 5 and 6 and
narrows 4. The numbers are kept so that citations stay stable.

1. **Trigger actions.** *Answered by Amendment 1 (A1.1).* Which actions update the aggregates.
   Candidates were: a run is finalized; an outcome score is attached to a decision or routing
   choice (ADR-058 §3); a decision is approved or corrected (ADR-060 §2 and §5).
2. **The aggregate model.** Whether aggregates are nodes, properties or both, how they are keyed,
   how ADR-057 §7's context dimensions are encoded, and how the model is versioned (ADR-057 Open
   Question 2, applied to the graph).
3. **Incremental update or periodic rebuild.** *Answered by Amendment 1 (A1.2): a full rebuild on
   each trigger, and a missed update is repaired by the next rebuild (A1.4).* The question was
   whether each trigger updates aggregates incrementally, whether a periodic or on-demand rebuild
   runs alongside, and how a missed update is detected. It meets ADR-057 Open Question 4
   (evaluator cadence and placement), whose placement half stays open.
4. **Separation from ADR-062's generations.** *Narrowed by Amendment 1 (A1.3):* the statistics use
   the same database and settings as ADR-062. Still open, and left to the build: how the mutable
   aggregates stay apart from ADR-062's immutable projection generations, for example by labels
   or by database name.
5. **An unreachable configured store.** *Answered by Amendment 1 (A1.4): retry.* ADR-057 Open
   Question 6 with the Neo4j settings. The review had recommended treating it like Mode 0 for that
   run, with one warning and a run limitation.
6. **Privacy of a shared store.** *Closed by Amendment 1 (A1.5): there is no shared store.* This
   was ADR-057 Open Question 1: which fields may leave the machine for a shared store, and in what
   form.
7. **Hosting.** Whether adopters run Neo4j themselves or use a hosted service, whether a managed
   Leafcutter service follows later, and what an adopter must run to turn learning on.

## Amendment 1 — 2026-10-02 — Open questions answered; each client has its own store

| Field | Value |
|---|---|
| Amends | Decision §2, §4 and the §5 table; Open Questions 1, 3, 4, 5 and 6 |
| Status | Accepted |
| Deciders | BrainCandy |
| Driven by | BrainCandy's answers of 2026-10-02 to this ADR's Open Questions |
| Supersedes | [ADR-057](ADR-057-colony-memory-store-optional-postgres.md) §8 (shared colony memory), which §5 had carried over |

BrainCandy answered the open questions on 2026-10-02:

> "any time an item that aggregates is added. I would start with rebuild as it is probably fast?
> yes same neo. retry if not available. statistics are build on other data, so should be fine
> anyways. shared store? ah... no each client needs their own. so it uses the neo from .env"

### A1.1 Trigger: every added item that feeds an aggregate

- The aggregates MUST be updated whenever an item that feeds an aggregate is added, for example
  a new outcome, decision or capability-gap record. This answers Open Question 1.
- This settles when the aggregates are updated, the cadence half of ADR-057 Open Question 4.
  Where the update runs, in-process or as a separate job, stays open.

### A1.2 Update strategy: a full rebuild first

- Each trigger MUST rebuild the aggregates in full. This answers Open Question 3.
- The choice rests on BrainCandy's expectation that a rebuild is fast. That expectation has not
  been measured.
- Incremental maintenance is a later optimisation. It MUST be introduced only if rebuilds prove
  too slow.

### A1.3 The same Neo4j as ADR-062

- The statistics MUST use the same Neo4j as ADR-062's knowledge retrieval, configured by the same
  `LEAFCUTTER_NEO4J_*` settings in the project `.env` (§4). Leafcutter MUST NOT add a separate
  set of Neo4j settings for statistics. This answers the database and credentials part of Open
  Question 4.
- How the mutable aggregates stay apart from ADR-062's immutable projection generations, for
  example by labels or by database name, is left to the build. Open Question 4 keeps only this
  part. Which of ADR-062's two credential pairs the statistics writes use is also left to the
  build.

### A1.4 An unavailable store: retry, and the next rebuild repairs

- When Neo4j is not available, Leafcutter MUST retry the update. The number of retries and the
  backoff are left to the build. This answers Open Question 5.
- Statistics are derived from other data: Langfuse, run records and decision records (§2). A
  missed or failed update is therefore repaired by the next rebuild (A1.2), and nothing is lost.
- Statistics MUST NOT block a run.

### A1.5 Each client has its own store

- Each client, meaning each Leafcutter installation or project, MUST have its own statistics
  store: the Neo4j configured in its own `.env`.
- There MUST NOT be a cross-client or team-shared colony memory. This supersedes ADR-057 §8,
  which §5 had carried over.
- With no shared store, the shared-store privacy question (Open Question 6, ADR-057 Open
  Question 1) falls away.

### Consequences of this amendment

- **Positive.** The first implementation needs one trigger rule and one update path, and a
  missed update needs no repair procedure of its own. Retrieval and statistics share one Neo4j
  and one set of settings. No context is pooled across clients.
- **Negative.** A full rebuild on every added item costs more as the history grows, and its speed
  is an expectation, not a measurement. ADR-057's team benefit is given up: evidence one client
  gathers does not reach another client's routing or calibration, so each store fills more
  slowly. Statistics and ADR-062's projections share one database, so keeping them apart rests on
  the build (Open Question 4).
- **Operational.** While Neo4j is unavailable, statistics lag until the next successful rebuild.
  Beyond retrying and never blocking a run, this amendment decides no behaviour for an
  unavailable store.

## References

- Source: BrainCandy's decision of 2026-10-02, quoted in Context, and BrainCandy's answers of the
  same day, quoted in Amendment 1.
- [ADR-057: Colony memory store, optional PostgreSQL](ADR-057-colony-memory-store-optional-postgres.md)
  (superseded in part by this ADR)
- [ADR-056: Colony memory, evidence reinforcement](ADR-056-colony-memory-evidence-reinforcement.md)
  (§1, §8, §9)
- [ADR-058: Langfuse is the colony history](ADR-058-langfuse-colony-history-scores-datasets.md) (§3, §6)
- [ADR-059: Decision store](ADR-059-decision-store-reviewable-yaml-records-now-graph-later.md);
  [ADR-060: Source of truth and approval authority](ADR-060-source-of-truth-and-approval-authority.md);
  [ADR-061: Identity of declared and learned records](ADR-061-identity-of-declared-and-learned-records.md)
- ADR-062 "Standalone Knowledge Retrieval over Immutable Git Projections" (branch
  `feature/knowledge-retrieval-v01`, not yet on main; cited without a link)
- Colony memory Stage 0 delta:
  [part 2](../../analysis/2026-10-01-colony-memory-stage0-delta-2-reuse-and-mvp.md) (row 14, Mode 0),
  [part 3](../../analysis/2026-10-01-colony-memory-stage0-delta-3-lessons-adrs-ownership.md) (ADR plan),
  [part 4](../../analysis/2026-10-01-colony-memory-stage0-delta-4-decisions-needed.md) (decisions 1, 2, 4)
- [Colony Memory component](../components/colony-memory.md);
  [Decision Kernel component](../components/decision-kernel.md)
- Code: `kernel/memory/port.py` (the port), `kernel/memory/backend.py` (backend selection)
