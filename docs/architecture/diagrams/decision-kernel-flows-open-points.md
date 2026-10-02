---
title: "Decision Kernel and Colony Memory — Open Points in the Designs"
description: "Numbered list of the places where the Decision Kernel, colony memory and legacy-pipeline sources are silent, disagree with each other, or disagree with the code on main, each with the exact sources involved and its status as re-checked on 2026-10-02. The flow and context pages point to these items instead of choosing an answer."
type: reference
flight_level: L3-Component
diagram_type: none
status: draft
parent: docs/architecture/diagrams/decision-kernel-flows-overview.md
created: 2026-09-30
last_updated: 2026-10-02
source_ticket: null
components:
  - decision_kernel
related_docs:
  - docs/architecture/diagrams/decision-kernel-flows-overview.md
  - docs/architecture/adrs/ADR-052-capabilities-replace-agents-prompts-are-compiled.md
  - docs/architecture/adrs/ADR-055-capability-registry-starts-empty.md
  - docs/architecture/adrs/ADR-056-colony-memory-evidence-reinforcement.md
  - docs/architecture/adrs/ADR-057-colony-memory-store-optional-postgres.md
  - docs/architecture/adrs/ADR-058-langfuse-colony-history-scores-datasets.md
  - docs/architecture/adrs/ADR-059-decision-store-reviewable-yaml-records-now-graph-later.md
  - docs/architecture/adrs/ADR-060-source-of-truth-and-approval-authority.md
  - docs/architecture/adrs/ADR-061-identity-of-declared-and-learned-records.md
  - docs/architecture/adrs/ADR-065-colony-learned-statistics-neo4j-aggregates.md
  - docs/analysis/2026-09-30-decision-kernel-design-3-kernel-scheduler.md
  - docs/analysis/2026-09-30-decision-kernel-design-4-jev-and-capabilities.md
  - docs/analysis/2026-09-30-decision-kernel-design-5-client-observability.md
tags:
  - decision-kernel
  - colony-memory
  - open-questions
---

# Decision Kernel and Colony Memory — Open Points in the Designs

The pages under the [Design Map](decision-kernel-flows-overview.md) map only what the sources
say. This list names every place where they are silent or disagree. It was written on 2026-09-30
against `feature/kernel-bootstrap-v0` and re-checked on 2026-10-02 against main, after PRs #973,
#977 and #978, ADR-059 to ADR-061 and [ADR-065](../adrs/ADR-065-colony-learned-statistics-neo4j-aggregates.md). Numbers are stable: a settled item
keeps its number. None is resolved here.

## Changes on 2026-10-02

| Change | Items |
|---|---|
| Settled | OP-02 (as-built note), OP-15 (implemented in PR #972), OP-17 (ADR-065 §6) |
| Partly settled | OP-04 and OP-08 (by the code), OP-05 (glossary read as text), OP-22 (record fields, ADR-061) |
| Narrowed by ADR-059 to ADR-061 | OP-03 (precedent never enters routing), OP-06 (Git is canonical) |
| Moved to ADR-065's open questions | OP-23, and the store parts of OP-19 and OP-25 |
| New | OP-26 to OP-33 |

## A. Context and capabilities

- **OP-01 Routing state: design and code differ. Open.** Design part 4 still sends
  `{"request": {kind, goal, question, payload_summary}, "task": {goal, component_ids}}`. The code
  (`kernel/scheduler/routing.py`) sends `task` plus `requests.<work_item_id>` with `kind`, `goal`,
  `question`, `payload_schema`, `payload_keys` and `clarifications`. The code's decision history
  explains the batching.
- **OP-02 The clarification return path. Settled.** Design part 3, "As built (intake intent)",
  now says how an answer is used: it becomes the primary statement of intent and is classified
  again, at most `intent.max_clarifications` times. Routing clarifications reach the routing
  state as `clarifications`.
- **OP-03 How learned statistics enter routing. Open, narrowed.** ADR-059 §5 and ADR-060 §4
  settle that precedent never enters routing; only learned statistics (ADR-065) will. Not stated:
  which fields, whether they go into the state or the criterion text, the new template version,
  and whether Jev or code weighs statistics against semantic fit (ADR-053 §5 keeps exact
  computation in code).
- **OP-04 Criteria edits: the code decides, the design says open. Partly settled.**
  `human_answer.v1` carries structured fields: `approved_option_ids`, `approved_criterion_ids`,
  `edited_criteria` (an entry with a proposal's id edits it, one without is new) and
  `added_options`. Free text is kept as a human input and a limitation, never turned into criteria
  (`kernel/capabilities/decision/approvals.py`). The earlier code that made each free-text line a
  criterion is gone. Design part 4 still says "Open for P5/P6: how an edit is expressed".
- **OP-05 The glossary as a retrieval source. Partly settled.** `docs/glossary.md` is a root of
  the `repo.docs` source, so research reads it as plain text. The knowledge-map `glossary` surface
  is still unused, and glossary-aware context stays Stage 2 (spec §17.1).
- **OP-06 No source-authority order. Open, narrowed.** ADR-060 §1 makes Git canonical over run
  artifacts, traces and any graph. It sets no precedence between repository sources (for example
  an ADR against `CLAUDE.md`). Spec §21 asks for "minimal explicit rules for MVP".
- **OP-07 Policies have no runtime home. Open.** ADR-054 level 2 has no V0 mechanism, spec §4.3
  excludes a policy engine from the MVP, and storage and format are undecided (ADR-054 open
  question 2). Component-scoped policies are Stage 3 (spec §18.4).
- **OP-08 The invocation compiler. Partly settled.** P8 built a deterministic compiler for host
  packets (`kernel/capabilities/host/compiler.py`): task statement and output requirements from
  the payload, schema, operations, cited evidence and limits, redacted and fingerprinted. Jev
  questions come from versioned templates. ADR-052 §3's full input list (capability definition,
  component policies, approved decisions) is not compiled in, and no source says whether one
  compiler for host packets, Jev questions and worker loops follows.
- **OP-09 Lifecycle transitions are unspecified. Open.** ADR-052 §4 names steps and outcomes, but
  not which check leads to which outcome, where REPAIR re-enters, or whether `needs_human` is
  REQUEST INFORMATION or ESCALATE. ADR-052 also leaves open whether the V0 graphs are restated
  in lifecycle terms.
- **OP-10 No executor for a coding worker before Stage 5. Open.** Stage 3 defines coding and
  testing views (spec §18.3), and Stage 5 adds direct coding executors (spec §20). No source says
  whether a Stage 3 worker runs as a Claude Code handoff, where every host operation forbids
  `edit_repository`, or waits for Stage 5.
- **OP-11 ADR-055's wording against retrieval. Open.** ADR-055 §2: the kernel "MUST NOT read,
  normalize or route over the legacy agent, skill, workflow or command registries". The default
  source `knowledge.components` still reads the knowledge-map surfaces `agents` and `skills`
  (`config/agent_registry.json`, `config/skill_registry.json`) as evidence. ADR-055's context is
  routing; its wording also forbids reading.
- **OP-12 The host LLM's ambient context. Open.** The host is a Claude Code session, so
  `CLAUDE.md`, auto-memory, skills and MCP prompts reach it next to the kernel packet. The
  `/leafcutter` skill pre-approves only `run`, `resume` and `status`, which limits tools but not
  context. Spec §2.3 and §11.5 name this; spec §20 brings fresh per-task context in Stage 5. No
  source says how ADR-052's compiled-instructions rule applies until then, or whether the kernel
  should record which ambient context was present.

## B. The legacy pipeline

- **OP-13 Injection builder: doc and code differ. Open.** `docs/architecture/components/injection-builder.md`
  says supervisors invoke it before spawning a phase agent and gather all 11 channels. The
  docstring of `scripts/injection_builders.py` says it builds tables injected into compiled
  agent templates at build time and exposes `assemble_context_bundle` for the fast lane.
- **OP-14 Two legacy topology docs disagree. Open.** `docs/agentic-runtime-flow.md` still draws
  epic-supervisor → ticket-supervisor → phase agents. `docs/architecture/agent_delivery_workflows.md`
  §4 records the ADR-019 correction: `build-feature.js` dispatches phase agents directly at
  depth 1. The design map follows the second.
- **OP-15 The skill name. Settled and implemented.** The user decided (2026-09-30) that the
  kernel skill is `/leafcutter` and the knowledge-hub command is renamed. PR #972 renamed the hub
  command to `/leafcutter-help`; the kernel skill installs with
  `python -m kernel install-skill --name leafcutter`.
- **OP-16 The legacy pipeline's future. Open.** ADR-052 and ADR-055 say both coexist, and the
  kernel is not shipped to adopters. No source says whether or when legacy agents retire, whether
  the kernel will ship to adopters, or which legacy assets are candidates for `legacy_admission`.

## C. Colony memory and learning

- **OP-17 Whether COLLECT starts inside V0. Settled by ADR-065 §6.** Learned statistics start
  only with the roadmap's COLLECT step, and ADR-065 does not change V0 scope; V0 merged without
  COLLECT. The ADR-056 §9 recording prerequisites are tracked as OP-26.
- **OP-18 Two roadmap tracks describe one store. Open.** `phase_kernel_4_trails` still says an
  analytics job "feeds a performance store". `phase_colony_1_collect` now names an optional Neo4j
  store. How the two tracks' exit criteria relate is not stated.
- **OP-19 The learning evaluator. Open; partly moved.** Which actions trigger an update, and
  incremental update versus rebuild, are ADR-065 open questions 1 and 3. Still open here: placement and
  inputs, including whether it reads the local `events.jsonl` (ADR-056 open question 5, ADR-057
  open question 4). Degraded runs are never re-exported, so an evaluator that reads only Langfuse
  undercounts them.
- **OP-20 Local gap records and the store. Open.** `gaps/observations.jsonl` stays the gap
  record. ADR-057 §6 made a `capability_gaps` table its cross-run counterpart, and ADR-065
  replaces tables with aggregates. How local observations reach the aggregates is not stated.
- **OP-21 Scores and datasets. Open.** ADR-058 decides them but "does not schedule" them; the
  roadmap's `phase_colony_2_analyze` lists them among its exit criteria, and the `Tracer` still
  has no score operation. Open: score names and owners, sampling and retention, where scores are
  written (ADR-058 open questions 1–3), and whether ADR-056 §9's outcome event is a Langfuse
  score, a local `RunEvent`, or both.
- **OP-22 Context dimensions. Partly settled.** Decision records carry `repository_id` (from
  `memory.repository_id`, else the scope's workspace id; ADR-061 §3), components, roadmap phase,
  `decision_type` and policy, template, model and kernel versions. Still missing: `task_type`
  anywhere and a decision type on observations (ADR-056 open question 4). Whether statistics
  reuse the records' `repository_id` is not stated.
- **OP-23 A configured store that cannot be reached. Moved to ADR-065** (open question 5). For
  decision records the code decides: a missing or invalid index, or a read error, gives no precedent and a warning,
  and `decisions validate` is what fails.
- **OP-24 Held-out cases. Open.** Spec §19.4 requires held-out evaluation, and ADR-058 notes that
  a case that motivated a change is not held out for it. How held-out cases are chosen is not
  stated.
- **OP-25 Further open questions carried from the ADRs. Open; partly moved.** Ground truth for
  "correct", the decay function, the exploration rate and automatic threshold changes (ADR-056
  open questions 3, 1, 2, 6); retention and the calibration bar for INFLUENCE ROUTING (ADR-057
  open questions 3, 7). Privacy of a shared store and schema versioning (ADR-057 open questions
  1, 2) now sit with ADR-065 (open questions 6 and 2).

## D. Found on 2026-10-02

- **OP-26 ADR-056 §9 recording prerequisites on main. New.** V0 merged. (1) No version fields
  sit next to `CorrelationIds`, which holds ids only; Jev generations carry template ids and
  versions, invocations carry `versions` (`host_template`), and decision records carry versions in
  provenance. (2) No outcome event keyed to `decision_id` exists; record corrections (ADR-060 §5)
  are the nearest form. (3) Countable gap records exist. The founding exit criterion asks that
  each is implemented or explicitly deferred by a recorded decision; no such record was found.
- **OP-27 Statistics on the `ColonyMemory` port. New.** ADR-065 §3 puts the graph backend on
  ADR-059's port, but `kernel/memory/port.py` has only `find_decisions`, `get_decision` and
  `stage_decision`, all synchronous. ADR-065 §3 leaves the statistics operations' names and
  signatures, and how one port instance serves file-backed records and graph-backed statistics,
  to the build. ADR-057's method sketch stays illustrative.
- **OP-28 Two switches, one port. New; settled 2026-10-02.** ADR-065 §4 now says: without Neo4j or
  with the opt-out, only learned statistics are off; decision records and precedent keep following
  `memory.backend` (`file` by default), and `NullColonyMemory` is selected only for
  `memory.backend: null`. Still open for the build: which backend `build_memory` composes when
  statistics are on. Original finding: `memory.backend` (`file` or `null`) turns decision
  records on or off; the `LEAFCUTTER_NEO4J_*` settings and `LEAFCUTTER_SELF_LEARNING=false` turn
  learned statistics on or off. ADR-065 §4 says that without a configured Neo4j store, or with the
  opt-out, startup MUST select `NullColonyMemory`. In code `NullColonyMemory` means "no precedent,
  nothing staged" (ADR-059 §2), so read literally §4 would switch precedent off in every install
  without Neo4j, against `memory.backend: file` as the default and ADR-059's "precedent from day
  one". ADR-065 §3 and its Negative consequences leave the composition to the build. Not stated:
  whether the opt-out also stops precedent, and which backend `build_memory` returns when only
  one kind is on.
- **OP-29 Host allowed operations: design and code differ. New.** Design part 4 lists finer
  allowed operations per host capability (`read_supplied_artifacts`, `propose_options`,
  `synthesize`, `read_repo_paths`, `web_fetch`). As built, a packet's `allowed_operations` is the
  descriptor's `operations` list, one name each (`generate_options`, `synthesize_evidence`,
  `bounded_research`, `formulate_question`), and the finer scope is prose in the compiled task
  statement.
- **OP-30 Rejection codes: design part 3 is stale. New.** Its resume section names
  `run_cancelled`, `stale_submission` and `kind_mismatch`. The code (`RejectionCode`) and design
  part 5 use `cancelled_or_superseded`, `not_pending`, `stale_revision`, `wrong_kind`,
  `actor_mismatch`, `forged_id`, `schema_invalid` and `semantic_invalid`.
- **OP-31 Decision records are not a research source. New.** No source in the default catalog
  covers `docs/decisions/`, so a `prior_decisions` research need never finds a record; records
  reach a decision only as precedent through the port. ADR-059 §3 says the knowledge map reads
  records through its `docs` surface, but no kernel source uses that surface. Whether research
  should also search records is not stated.
- **OP-32 Corrections and the learning loop. New.** A published correction
  (`decisions publish --correct`, ADR-060 §5) is a human-confirmed wrong decision keyed by its
  `dec-` id. No source says whether it also becomes a Langfuse score, a dataset case (ADR-058 §4)
  or a statistics update, or how it relates to ADR-056 §9's outcome event.
- **OP-33 Design file names that do not exist on main. New.** Design part 1's module map and
  design part 4 name `scheduler/routing_templates.py`, `nodes_integration.py`, `nodes_finalize.py`,
  `capabilities/host/operations.py` and `capabilities/host/conversion.py`; design part 5's CLI
  heading names `adapters/envelope.py`. On main the routing template is in `scheduler/routing.py`,
  the nodes are `nodes_integrate.py` and `nodes_lifecycle.py`, each host operation has its own
  module with a `convert`, accepted submissions are converted in `kernel/interaction/results.py`,
  and the envelope is `kernel/service_envelope.py`. The module map also lacks `intent/` and
  `memory/`.

## Settled so far

- The colony store's stages: ADR-057 §10, carried over by ADR-065, and the roadmap's
  `phase_colony_*` phases. Statistics start only with COLLECT (ADR-065 §6).
- ADR-056's "performance store" is ADR-057's "colony memory store" (ADR-057 §1); ADR-065 keeps it
  in Neo4j as derived aggregates.
- The statistics store is Neo4j, not PostgreSQL, holding derived aggregates that are rebuildable
  and never canonical; `LEAFCUTTER_COLONY_DB_URL` is history only, and
  `LEAFCUTTER_SELF_LEARNING=false` stays the opt-out (ADR-065 §1, §2, §4).
- Approved decisions are YAML records in `docs/decisions/` behind the `ColonyMemory` port, and
  precedent is evidence from day one (ADR-059).
- Git is canonical; only a human approval creates a record; the kernel never writes the
  repository during a run (ADR-060).
- Decisions get `dec-<16hex>` ids, stable across the pauses of one decision; records are keyed by
  `(repository_id, kind, id)` (ADR-061).
- `host.research` is `fixed` with operation `bounded_research` in both design part 2 and
  `config/capability_registry.json`.

## Cross-Links

- Parent: [Design Map](decision-kernel-flows-overview.md)
- Open questions at their source: [ADR-052](../adrs/ADR-052-capabilities-replace-agents-prompts-are-compiled.md),
  [ADR-054](../adrs/ADR-054-process-representation-and-maturity-model.md),
  [ADR-056](../adrs/ADR-056-colony-memory-evidence-reinforcement.md),
  [ADR-057](../adrs/ADR-057-colony-memory-store-optional-postgres.md),
  [ADR-058](../adrs/ADR-058-langfuse-colony-history-scores-datasets.md),
  [ADR-065](../adrs/ADR-065-colony-learned-statistics-neo4j-aggregates.md),
  [design part 6 risks](../../analysis/2026-09-30-decision-kernel-design-6-tests-phases-risks.md)
