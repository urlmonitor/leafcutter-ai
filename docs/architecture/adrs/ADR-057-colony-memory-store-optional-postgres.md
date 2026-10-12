---
title: "ADR-057: Colony Memory Store — Optional PostgreSQL Behind a ColonyMemory Port"
description: "ADR-056's performance store becomes the colony memory store: compact, context-dimensioned learned statistics in plain PostgreSQL, reached through a standard connection URL from the project-root .env and hidden behind one ColonyMemory port whose Null implementation keeps the rest of the kernel working. Cross-run learning is optional, the hot path never queries Langfuse, and any Postgres host works, a Supabase project included. Superseded in part by ADR-065 (2026-10-02): learned statistics live in Neo4j as derived aggregates behind ADR-059's ColonyMemory port; optionality with a Null default, the hot-path rule, context dimensions, the run root and the staging ladder stay in force. ADR-065 Amendment 1 (2026-10-02) also supersedes §8: each client has its own store, and there is no shared colony memory."
type: "adr"
status: "active"
created: "2026-09-30"
last_updated: "2026-10-02"
deciders:
  - BrainCandy
components:
  - decision_kernel
  - colony_memory
related_docs:
  - docs/architecture/adrs/ADR-056-colony-memory-evidence-reinforcement.md
  - docs/architecture/adrs/ADR-058-langfuse-colony-history-scores-datasets.md
  - docs/architecture/adrs/ADR-065-colony-learned-statistics-neo4j-aggregates.md
  - docs/architecture/adrs/ADR-053-intelligence-selection-deterministic-jev-llm-human.md
  - docs/architecture/adrs/ADR-054-process-representation-and-maturity-model.md
  - docs/architecture/components/colony-memory.md
  - docs/architecture/components/decision-kernel.md
  - docs/analysis/2026-09-30-decision-kernel-design-2-contracts-registry-config.md
  - docs/analysis/2026-09-30-decision-kernel-design-3-kernel-scheduler.md
  - docs/analysis/2026-09-30-decision-kernel-design-5-client-observability.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-5-client-observability-safeguards.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-7-later-stages.md
  - tickets/00_inbox/TICKET-20260930-KernelBootstrapV0.md
related_code:
  - kernel/
  - kernel/secrets.py
---

# ADR-057: Colony Memory Store — Optional PostgreSQL Behind a ColonyMemory Port

## Status

| Field | Value |
|---|---|
| Status | Accepted, superseded in part |
| Date | 2026-09-30 |
| Superseded in part by | [ADR-065](ADR-065-colony-learned-statistics-neo4j-aggregates.md), 2026-10-02; §8 by [ADR-065 Amendment 1](ADR-065-colony-learned-statistics-neo4j-aggregates.md#amendment-1--2026-10-02--open-questions-answered-each-client-has-its-own-store), 2026-10-02. See the note below. |
| Deciders | BrainCandy |
| Author | `adr-author`, recording BrainCandy's binding decisions from the 2026-09-30 Langfuse and colony-memory-store discussion |
| Supersedes | None. Names and places the "performance store" of [ADR-056](ADR-056-colony-memory-evidence-reinforcement.md) §8, and answers the first half of ADR-056 Open Question 5 (where the store lives and its format). |

> **Read together with [ADR-065](ADR-065-colony-learned-statistics-neo4j-aggregates.md), which
> supersedes this ADR in part (2026-10-02).** The learned-statistics store is Neo4j, not
> PostgreSQL. **Superseded:** §1's store technology, §2, the §3 PostgreSQL implementation, §4's
> `LEAFCUTTER_COLONY_DB_URL` (replaced by the `LEAFCUTTER_NEO4J_*` settings), §6 (relational tables
> become derived aggregates in the graph), and the PostgreSQL and Supabase side of the
> Alternatives. **Also superseded, by
> [ADR-065 Amendment 1](ADR-065-colony-learned-statistics-neo4j-aggregates.md#amendment-1--2026-10-02--open-questions-answered-each-client-has-its-own-store)
> (2026-10-02):** §8. Each client has its own store, the Neo4j configured in its own `.env`, and
> there is no shared colony memory. The same amendment closes Open Questions 1 (shared-store
> privacy) and 6 (an unreachable store is retried). **Still in force:** the store is optional with
> `NullColonyMemory` as the default and is chosen once at startup (§3), the
> `LEAFCUTTER_SELF_LEARNING=false` opt-out (§4), and §5, §7, §9 and §10. The `ColonyMemory` port
> itself is now defined by
> [ADR-059](ADR-059-decision-store-reviewable-yaml-records-now-graph-later.md)
> (`kernel/memory/port.py`). The text below is unchanged; where it names PostgreSQL, Supabase,
> `LEAFCUTTER_COLONY_DB_URL` or a shared store, it describes the superseded design.

## Context

[ADR-056](ADR-056-colony-memory-evidence-reinforcement.md) §8 separates observability from
operational state: Langfuse feeds an analytics or evaluation job, the job writes compact routing
statistics into a "Leafcutter performance store", and the kernel reads only that store. Runtime
routing MUST NOT query Langfuse. ADR-056 left open where that store lives and in which format
(Open Question 5).

The 2026-09-30 follow-up discussion settled Langfuse as the primary tracking and evaluation layer.
[ADR-058](ADR-058-langfuse-colony-history-scores-datasets.md) records that part. For the store, the
assistant proposed "something as simple as Postgres initially". BrainCandy then proposed Supabase:
an adopter would not install their own database, but add credentials to `.env`, and without
credentials self-learning would stay off. BrainCandy's binding instruction afterwards narrowed
this: the store is **plain PostgreSQL, not the Supabase API**. Supabase remains an option only
because a Supabase project provides a Postgres connection URL.

The decision is needed now, before the Decision Kernel
([TICKET-20260930-KernelBootstrapV0](../../../tickets/00_inbox/TICKET-20260930-KernelBootstrapV0.md))
writes its first learned statistic:

1. **Vendor lock-in.** The discussion's first concrete proposal was Supabase. Built on its client
   library and its REST, key and auth model, self-learning would depend on one hosting vendor, and
   a local or self-hosted database would not work.
2. **Optionality spreads.** Without one port chosen at startup, every caller checks whether a
   database is configured, and `if settings.<db_url>:` branches accumulate across the kernel.
3. **Global rates mislead.** A statistic without context says a capability is good everywhere
   because it did well on one kind of task. That is a misleading pheromone trail.
4. **The hot path must stay simple.** Routing reads statistics on every decision. Querying raw
   traces there is what ADR-056 §8 already rules out.

## Decision

### 1. The colony memory store is ADR-056's performance store: the pheromone map

The store that ADR-056 §8 calls the "Leafcutter performance store" MUST be called the **colony
memory store**. It is the pheromone map of the colony model (ADR-056 §1). It holds compact learned
statistics that can inform routing, and the decision outcome records those statistics are computed
from. Detailed observational evidence (complete traces, model calls, retrieval, costs and latency
per step) is not the store's job: Langfuse keeps it as the colony history (ADR-058).

> **Langfuse remembers what happened. The colony memory store remembers what Leafcutter learned.**

Langfuse answers "What actually happened?". The colony memory store answers "What has the colony
learned?": success rates, wrong decisions, preferred paths, confidence calibration, capability
gaps and routing statistics.

### 2. Plain PostgreSQL, reached by a standard connection URL

- The colony memory store MUST be a PostgreSQL database. Leafcutter MUST connect to it with a
  standard Postgres driver and a standard Postgres connection URL.
- Leafcutter MUST NOT use the Supabase client library, PostgREST or any other REST API over the
  database, and MUST NOT depend on Supabase auth or row-level security.
- Any Postgres-compatible host MUST work: a local, self-hosted or managed Postgres. A Supabase
  project works when the adopter pastes its **Postgres connection string**. Its project REST URL
  and anon key are not used.
- The implementation MUST be named for Postgres, not for a vendor. There is no
  "SupabaseColonyMemory".
- The exact driver and its version pin are left to the build.

### 3. Optional, behind one `ColonyMemory` port chosen once at startup

- All access to the colony memory store MUST go through one port, `ColonyMemory`. Its two
  implementations are a Postgres-backed implementation and `NullColonyMemory`.
- The implementation MUST be chosen once, at startup. Code outside that selection MUST NOT branch
  on whether a database URL is configured. There are no `if settings.<db_url>:` branches anywhere
  else.
- Without a store, the kernel, Jev, LangGraph, the Claude Code handoff and Langfuse tracing MUST
  all keep working. Only cross-run learning is off.
- The port's method list is ILLUSTRATIVE. The source sketches `get_capability_stats`,
  `record_capability_outcome`, `record_decision_outcome`, `get_path_stats` and
  `record_capability_gap`. Names, signatures and whether they are async are left to the build.

### 4. Configuration: two variables in the project-root `.env`

The store is configured in the project-root `.env`, the existing secrets convention of the kernel
([design part 2](../../analysis/2026-09-30-decision-kernel-design-2-contracts-registry-config.md),
"Secrets", which already holds `JEV_API_KEY` and the `LANGFUSE_*` keys). These two names are
decided:

| Variable | Meaning |
|---|---|
| `LEAFCUTTER_COLONY_DB_URL` | Postgres connection URL. When it is present, self-learning is enabled. |
| `LEAFCUTTER_SELF_LEARNING=false` | Explicit opt-out for someone who has a URL configured but does not want learning. |

Enablement is inferred. With `LEAFCUTTER_COLONY_DB_URL` present and no opt-out, startup MUST
select the Postgres implementation. Without the URL, or with `LEAFCUTTER_SELF_LEARNING=false`,
startup MUST select `NullColonyMemory`. The configuration MUST NOT name Supabase keys.

### 5. The hot path reads the store, never Langfuse

- The kernel MUST read learned statistics only from the colony memory store, through the port.
  It MUST NOT query Langfuse for runtime learning. This applies ADR-056 §8 to the named store,
  including its rule that statistics MUST NOT override the deterministic eligibility exclusions
  that run before Jev ([ADR-053](ADR-053-intelligence-selection-deterministic-jev-llm-human.md) §5).
- A **learning evaluator** MUST fill the store. It distils completed-run outcomes into the store,
  either from Langfuse traces and scores or directly at run end:

```text
Execution → Langfuse trace + scores → final outcome known → learning evaluator
          → colony memory store (PostgreSQL, via ColonyMemory) → kernel hot path
```

- When and where the evaluator runs is open (see Open Questions).

### 6. The learning layer is conventional tables; the starting tables are illustrative

The learning layer MUST stay conventional relational tables. The four starting tables below are
ILLUSTRATIVE, not a schema. Their names, and every column the source mentions, are left to the
build.

| Table | Purpose |
|---|---|
| `capability_stats` | Which graphs and capabilities work well for which situations |
| `decision_outcomes` | What Jev decided, and whether it was later confirmed or corrected |
| `path_stats` | Successful recurring graph and node sequences |
| `capability_gaps` | Tasks Leafcutter could not solve natively |

`decision_outcomes` is the raw material for the per-decision-type calibration that ADR-056 §4
requires. `capability_gaps` is the cross-run counterpart of the gap pressure in ADR-056 §6.

### 7. Context dimensions are mandatory

- Every statistic MUST be recorded with its context. A global success rate MUST NOT be recorded.
- The minimum dimensions are **capability, task_type, component, repository/project and
  policy_version**.
- Framework, language and decision_type are added later through a context signature. How the
  dimensions are encoded is left to the build.

The target is a statement like "decision_research has a 97% success rate for architectural
decisions involving LangGraph in this repository" (ILLUSTRATIVE), never "decision_research
success = 96%". `policy_version` is the store's side of ADR-056 §3 rule 2, which scopes evidence
to the versions that produced it.

### 8. The store supports a shared colony memory

A team MUST be able to point all its developers and CI at one colony memory store, so that
evidence one person discovers (a well-performing path, a wrong decision) improves routing and
calibration for everyone. This is how the colony metaphor works: workers contribute evidence to a
shared environment. Shared use is a later step. Its privacy rules are open (see Open Questions).

### 9. The store does not replace the V0 run root

The V0 run root, `.leafcutter/kernel/`
([design part 3](../../analysis/2026-09-30-decision-kernel-design-3-kernel-scheduler.md)),
MUST remain the local, authoritative operational state of runs on a machine: checkpoints, run
records, event logs, artifacts, the interaction ledger and local gap observations. The colony
memory store holds cross-run learned statistics only. It MUST NOT replace checkpoints or run
records, and the kernel MUST NOT use it as its checkpointer. This mirrors spec §12.2, in which the
durable local record is authoritative for workflow state
([spec part 5](../../analysis/2026-09-30-leafcutter-kernel-spec-rev3-5-client-observability-safeguards.md)).

### 10. Staged adoption: collect before anything influences routing

The colony memory store is adopted in five stages. The source's phase numbers and version labels
(MVP, V1, V2, V3) are shown for traceability.

| Stage | Source | What it does | Place in ADR-056 §9 and the kernel stages |
|---|---|---|---|
| COLLECT | Phase 1, MVP | Store optional. Record graph usage, decisions, outcomes, capability gaps and fallback usage. No behavioural influence. | Consumes ADR-056 §9's Stage 1 recording prerequisites (version fields, outcome events keyed to `decision_id`, countable gaps). Earliest start: right after kernel V0. |
| ANALYZE | Phase 2, V1 | Derive statistics and show them: success rates, common paths, wrong decisions, confidence calibration. | ADR-056 §9 Stage 4: analytics job, per-type calibration. |
| SUGGEST | Phase 3 | Suggest, for example "historically this path performs better". Routing does not change. | ADR-056 §9 Stage 4. |
| INFLUENCE ROUTING | Phase 4, V2 | Feed historical evidence into Jev routing. | ADR-056 §9 "4 or later": reinforcement-informed routing. |
| EVOLVE | V3 | Detect recurring capability gaps, weak policies, candidate workflows and repeated LLM reasoning. | ADR-056 §5 (POLICY GAP), §6 (gap pressure) and §7 (promotion under [ADR-054](ADR-054-process-representation-and-maturity-model.md)); ADR-056 §9 places these proposals in Stage 4. |

ADR-056 §9 places the performance store in Stage 4. This ADR lets COLLECT write to the store
earlier, right after V0, because COLLECT only records and influences nothing. Analysis and
everything after it stay where ADR-056 §9 puts them.

- Historical statistics MUST NOT change routing before INFLUENCE ROUTING. INFLUENCE ROUTING MUST
  start only after calibration, and only after it passes the held-out evaluation of spec §19.4
  ([spec part 7](../../analysis/2026-09-30-leafcutter-kernel-spec-rev3-7-later-stages.md)).
  Otherwise early accidental successes cause self-reinforcing bad behaviour.
- EVOLVE MUST produce proposals only. Turning one into a policy, workflow or registry entry
  remains a reviewed step (ADR-056 §3 rule 5).
- Each stage MUST show a colony-health improvement before it is reported as strengthening the
  colony (ADR-056 §9).
- **This ADR does not change kernel V0 scope.** The earliest start for COLLECT is right after V0.
  Starting COLLECT inside V0 is a decision for the V0 build, not for this ADR.

## Consequences

### Positive

- Leafcutter runs without any database. Cross-run learning is opt-in through one `.env` variable.
- Any Postgres host works. A Supabase project works through its connection string, so the
  convenience BrainCandy wanted is kept without tying Leafcutter to the Supabase API, keys or auth.
- The optional dependency lives behind one port selected once. The rest of the kernel stays free
  of configuration branches and behaves the same with or without a store, except for what it
  learns.
- The hot path reads compact statistics from one store and does not depend on Langfuse's
  availability or latency.
- Mandatory context dimensions keep one repository's or one task type's success from reading as a
  global trail.
- A shared store lets a team's evidence accumulate in one colony instead of per laptop.

### Negative

- Full learning needs two systems (Langfuse and Postgres) plus an evaluator between them.
- Learning is off by default. Users without a database contribute no evidence, and a single
  user's store stays small. Mandatory dimensions split the data further, so early statistics are
  noisy (ADR-056, Negative).
- Without Supabase auth and row-level security, access control for a shared store rests on
  Postgres itself: its roles and credentials.
- A shared store sends context out of the machine. Repository, component and task-type
  dimensions describe the work being done. The kernel ticket's risk surface is `privacy`.
- Schema changes become Leafcutter's responsibility across every adopter's database.
- A Postgres driver joins the kernel's dependencies.
- An evaluator that reads only Langfuse undercounts runs whose telemetry was spooled in degraded
  mode, which V0 does not re-export
  ([design part 5](../../analysis/2026-09-30-decision-kernel-design-5-client-observability.md)).

### Operational

- `.env` gains two optional variables, `LEAFCUTTER_COLONY_DB_URL` and
  `LEAFCUTTER_SELF_LEARNING`. It gains no Supabase keys.
- A Postgres connection URL normally embeds a password, so it is a credential under the existing
  secrets convention (design part 2): never logged, reported only as present or absent, and
  subject to redaction before telemetry export.
- A Supabase adopter copies the Postgres connection string from the project, not the REST URL or
  the anon key.
- Review rejects a branch on the database URL outside the startup selection, and a statistic
  recorded without the minimum context dimensions.
- The ADR-056 §9 Stage 1 recording prerequisites stay a recommendation to the V0 build. COLLECT
  depends on them, because traces recorded without them cannot be distilled later.

## Alternatives

- **Supabase API or client library** (supabase-py, PostgREST, Supabase auth and RLS). Rejected by
  BrainCandy. It ties the store to one vendor's REST, key and auth model, so a local or
  self-hosted Postgres would not work. Supabase stays usable through its Postgres connection URL.
- **Langfuse as the live store.** Rejected. Every routing decision would wait on a remote query of
  raw traces, routing would depend on a service the spec allows to be unavailable (§12.4), and
  degraded-mode runs never reach it. ADR-056 §8 already forbids runtime routing that reads Langfuse.
- **SQLite or local files only.** Rejected. A local file cannot be shared by a team and CI, so
  evidence one developer discovers never reaches anyone else's routing or calibration (§8). The
  V0 run root keeps its SQLite checkpoints; that is operational state, not colony memory.
- **A mandatory store.** Rejected. Every adopter would have to provision Postgres before the
  kernel runs at all, although the kernel, Jev, LangGraph, the Claude Code handoff and Langfuse
  tracing need no cross-run learning to work.
- **A custom tracing backend** as the evaluator's source. Rejected. Langfuse already exposes
  traces, scores, metrics and observations through its APIs and SDK, so the store can be derived
  from it. A custom backend would duplicate the observability layer ADR-058 settles on.

## Open Questions

This ADR explicitly does not decide:

1. **Privacy and data minimisation for a shared store.** Which fields may leave the machine
   (repository and component names, task types, context signatures, costs), and in what form. The
   kernel ticket's risk surface is `privacy`, so this must be settled before shared use.
2. **Migrations and schema versioning.** How the schema is created and upgraded in every adopter's
   database, and how a Leafcutter version finds a store written by another version.
3. **Retention and decay.** How long statistics and outcome records are kept, and how they fade.
   This is ADR-056 §3 rule 2 (evaporation) and its Open Question 1 applied to the store.
4. **Evaluator cadence and placement.** Periodic or right after a completed run, in-process or as a
   separate job, and whether it also reads the local `events.jsonl` records (the second half of
   ADR-056 Open Question 5).
5. **Multi-repository identity.** How the repository/project dimension identifies one repository
   stably across clones, forks, machines and CI.
6. **An unreachable configured store.** How the kernel behaves when `LEAFCUTTER_COLONY_DB_URL` is
   set but the database cannot be reached. The source is silent.
7. **The calibration bar for INFLUENCE ROUTING.** What counts as "after calibration" per decision
   type (ADR-056 §4), beyond passing the spec §19.4 evaluation.

## References

- Source: the 2026-09-30 discussion between BrainCandy and an assistant on Langfuse and the
  colony memory store, endorsed by BrainCandy, and BrainCandy's binding instruction of the same
  day (plain PostgreSQL, Supabase only through its connection URL, Postgres and Null
  implementations, a database-URL variable).
- Originating work: [TICKET-20260930-KernelBootstrapV0](../../../tickets/00_inbox/TICKET-20260930-KernelBootstrapV0.md)
- [ADR-056: Colony memory — evidence reinforcement](ADR-056-colony-memory-evidence-reinforcement.md)
  (parent; §1, §3–§9 and Open Questions 1 and 5)
- [ADR-058: Langfuse is the colony history — every node traced, decisions scored, datasets as regression memory](ADR-058-langfuse-colony-history-scores-datasets.md)
  (sibling; the history layer)
- [ADR-053](ADR-053-intelligence-selection-deterministic-jev-llm-human.md) §5;
  [ADR-054](ADR-054-process-representation-and-maturity-model.md) (promotion)
- [Colony Memory component](../components/colony-memory.md);
  [Decision Kernel component](../components/decision-kernel.md)
- Kernel design [part 2](../../analysis/2026-09-30-decision-kernel-design-2-contracts-registry-config.md)
  (secrets), [part 3](../../analysis/2026-09-30-decision-kernel-design-3-kernel-scheduler.md)
  (run root), [part 5](../../analysis/2026-09-30-decision-kernel-design-5-client-observability.md)
  (Langfuse, degraded mode); kernel spec Rev 3
  [part 5](../../analysis/2026-09-30-leafcutter-kernel-spec-rev3-5-client-observability-safeguards.md)
  (§12.2, §12.4) and [part 7](../../analysis/2026-09-30-leafcutter-kernel-spec-rev3-7-later-stages.md)
  (§19.4)
