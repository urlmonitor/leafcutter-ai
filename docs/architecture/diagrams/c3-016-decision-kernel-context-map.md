---
title: "Decision Kernel Context Map — Who Gets Which Context, and How Legacy Agents Differ"
description: "L3 data flow of where every Decision Kernel consumer gets its context: the intake intent and routing Jev calls, the decision and research Jev calls (including precedent from approved decision records), the host LLM, a planned bounded worker loop and the human. Names the source, the assembler and the stage of each context piece, lists planned sources (learned statistics, the Stage 2 context compiler, ADR-062 knowledge retrieval), and contrasts this with how legacy Claude Code agents receive context through the 11-channel knowledge plane."
type: architecture
flight_level: L3-Component
diagram_type: data_flow
status: draft
parent: docs/architecture/diagrams/c2-007-decision-kernel-flows-overview.md
created: 2026-09-30
last_updated: 2026-10-02
source_ticket: null
components:
  - decision_kernel
related_docs:
  - docs/architecture/agent_knowledge_plane.md
  - docs/architecture/components/injection-builder.md
  - docs/architecture/components/colony-memory.md
  - docs/analysis/2026-09-30-decision-kernel-design-4-jev-and-capabilities.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-2-runtime-and-registry.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-7-later-stages.md
  - docs/architecture/adrs/ADR-052-capabilities-replace-agents-prompts-are-compiled.md
  - docs/architecture/adrs/ADR-059-decision-store-reviewable-yaml-records-now-graph-later.md
  - docs/architecture/adrs/ADR-065-colony-learned-statistics-neo4j-aggregates.md
related_code:
  - kernel/intent/classify.py
  - kernel/scheduler/routing.py
  - kernel/capabilities/retrieval/
  - kernel/capabilities/host/compiler.py
  - kernel/memory/precedent.py
  - config/kernel_config.default.json
  - config/capability_registry.json
  - scripts/injection_builders.py
tags:
  - decision-kernel
  - context
  - knowledge-plane
---

# Decision Kernel Context Map — Who Gets Which Context

In the kernel no consumer receives "the context". Each call gets a small, typed input that
kernel code assembles from named sources. This page shows the whole picture. Three detail pages
list every context piece with its exact source, its assembler and the stage it arrives in.

A capability receives only its validated request, the relevant evidence references or excerpts,
its constraints and its execution context. It does not receive the whole repository or the whole
run history by default (spec §5).

```mermaid
flowchart LR
  subgraph SRC["Context sources"]
    TI["TaskInput - goal, scope, constraints, initial evidence, payload"]
    CFG[("capability_registry.json and kernel_config")]
    REPO[("Repo text roots and knowledge-map surfaces")]
    MEM[("docs/decisions - approved records via the ColonyMemory port")]
    RUN["Run state - evidence, findings, options, child outcomes, human answers"]
    COL[("Planned - learned statistics, Neo4j, ADR-065")]
    LATER["Planned - Stage 2 context, policies, ContextBundle; ADR-062 knowledge retrieval, not on main"]
  end
  subgraph ASM["Assembled by kernel code"]
    ROUTE["intake intent and route node"]
    GRAPHS["decision and research graphs, retrieve.repository"]
    PKT["open_interactions - compiled host packets"]
    COMP["Planned - compiler for worker loops"]
  end
  JEV["Jev calls - intent, routing, decision, research"]
  HOST["Host LLM - Claude Code"]
  HUM["Human"]
  WRK["Planned - bounded worker loop"]
  TI --> ROUTE
  CFG --> ROUTE
  RUN --> ROUTE
  COL -.-> ROUTE
  TI --> GRAPHS
  CFG --> GRAPHS
  REPO --> GRAPHS
  MEM -->|"precedent"| GRAPHS
  RUN --> GRAPHS
  LATER -.-> GRAPHS
  RUN --> PKT
  LATER -.-> COMP
  RUN -.-> COMP
  ROUTE --> JEV
  GRAPHS --> JEV
  PKT --> HOST
  PKT --> HUM
  COMP -.-> WRK
```

Parent: [Decision Kernel and Colony Memory — Design Map](c2-007-decision-kernel-flows-overview.md)

## Consumers

| Consumer | Receives, in short | Assembled by | Available from | Detail |
|---|---|---|---|---|
| Intake intent Jev call | The goal (or the clarified goal), component ids, earlier clarification answers, five answer kinds plus `__NEEDS_CONTEXT__` | First `route` pass, `kernel/intent/classify.py`, template `kernel.intent` v1 | V0 | [Jev calls](c3-017-decision-kernel-context-jev.md) |
| Routing Jev call | Task goal and component ids, the request, the descriptions of eligible `semantic` capabilities, the `__NONE__` and `__NEEDS_CONTEXT__` choices, earlier clarification answers | `route` node with the routing template (`kernel/scheduler/routing.py`) | V0. Learned statistics: INFLUENCE ROUTING (Stage 4 or later, store per ADR-065) | [Jev calls](c3-017-decision-kernel-context-jev.md) |
| Decision Jev calls (`assess`: kind, sufficiency, satisfaction, missing knowledge, preference, conflict, precedent) | Question, options, approved criteria, evidence excerpts, findings, constraints, **precedent candidates and precedent evidence** | Decision graph: `load`, `precedent`, templates in `assess` | V0. Precedent: V0, decision store (ADR-059 §5). Policies: Stage 3. Glossary-aware context: Stage 2 | [Jev calls](c3-017-decision-kernel-context-jev.md) |
| Research capability and its retrieval | Research question, evidence needs, category descriptions, source catalog, option context, search candidates | Research graph, `retrieve.repository` | V0. Context compiler: Stage 2. ADR-062 knowledge retrieval: in progress, not on main | [Research](c3-018-decision-kernel-context-research.md) |
| Host LLM (Claude Code) | A `HostWorkRequest`: operation, compiled task statement, input artifacts, evidence ids, allowed and forbidden operations, output schema. Also its own session context | `open_interactions`; the task statement is compiled by `kernel/capabilities/host/compiler.py` | V0 | [Host, worker, human](c3-019-decision-kernel-context-host-worker-human.md) |
| Bounded worker loop (for example coding) | A compiled view of the implementation contract: operation, task, approved decisions, evidence, constraints, expected output | A compiler for worker loops and the context compiler, both planned | Later: inputs in Stages 2–3, executor in Stage 5 | [Host, worker, human](c3-019-decision-kernel-context-host-worker-human.md) |
| Human | A `HumanQuestion`: question, choices with consequences, free-text and structured-answer rules, why research cannot settle it. Includes the precedent reuse question and the ranked design choice | `open_interactions`, with template wording or `host.formulate_question` | V0 | [Host, worker, human](c3-019-decision-kernel-context-host-worker-human.md) |

## Rules that hold for every kernel consumer

- **Kernel code assembles, models do not.** The kernel, never a model, assigns IDs, root
  identity and execution permissions (spec §7.2). Model instructions are compiled
  deterministically, never improvised by an LLM (ADR-052 §3).
- **Evidence is not instruction.** Retrieved text and precedent summaries are quoted into Jev
  state as values only, never interpolated into a template (design part 4, spec §13.3).
- **Every piece is traceable.** Evidence carries a locator, a source version (commit and dirty
  flag), a content hash and provenance. Every Jev call records its template id and version and an
  input fingerprint (spec §7.3, design part 4).
- **Secrets are masked before sending.** The redactor masks Jev state and host packets. Retrieval
  skips `.env*`, keys, `.security-allowlist` and `.git` (design parts 2 and 5).
- **Git is canonical; runs and traces are not.** A published decision record is the canonical
  form of a decision; run artifacts and Langfuse traces are operational history (ADR-060 §1).
- **Precedent is evidence, never authority.** It reaches decision calls only, never the routing
  call, and never changes a score or threshold (ADR-060 §4).
- **The runtime never reads Langfuse.** Learned context reaches routing only as compact
  statistics from the learned-statistics store (ADR-056 §8, ADR-057 §5,
  [ADR-065](../adrs/ADR-065-colony-learned-statistics-neo4j-aggregates.md)).
- **Legacy registries are never candidates.** Only `config/capability_registry.json` supplies
  routing choices (ADR-055).

**Planned sources, not on main.** ADR-062, "Standalone Knowledge Retrieval over Immutable Git
Projections", is accepted on branch `feature/knowledge-retrieval-v01` and not yet merged. It plans
a separate retrieval package over immutable Neo4j projections of Git whose port the composition
root injects into the capability mechanism, with results converted into the kernel's `Evidence`
contract. Until it merges, research reads only the V0 sources on the
[research page](c3-018-decision-kernel-context-research.md).

## Contrast: how legacy agents get their context

Legacy agents are Claude Code sub-agents. The harness assembles their context at spawn from the
[11-channel knowledge plane](../agent_knowledge_plane.md).

| Aspect | Legacy agent | Kernel consumer |
|---|---|---|
| What receives context | An agent: a persona prompt that carries the process inside it (ADR-052, Context) | One step: a Jev question, a host operation or a human question |
| Who assembles it | The Claude Code harness at spawn. `build.py` compiles registry tables into agent templates (`scripts/injection_builders.py`). The fast lane builds a layered bundle (`assemble_context_bundle`: architecture and high-level ACs, then prior tests, prior outputs and the working diff) | Deterministic kernel code for each call: the intent and `route` steps, the capability graphs, the retrieval adapter, the host packet compiler |
| What goes in | Whole channels: `CLAUDE.md`, auto-memory, MCP prompts, the glossary through `CLAUDE.md`, auto-loaded skills, agent frontmatter, harness config, the ticket via `ticket_path`, folder `README.md`, `PROJECT_CONTEXT.md`, on-demand skills | Only what the step needs: the request, evidence by id or as capped excerpts, criteria, constraints, precedent |
| How relevance is decided | The agent reads more on its own (Read, Grep, on-demand skills) | Jev selects evidence needs, reranks candidates and judges whether a precedent applies. Code searches, filters and caps. Jev decides only against supplied criteria |
| Where the process lives | In the agent prompt and its skills | In graphs, configuration and checks. Prompts are compiled outputs (ADR-052) |
| Precedence | "Specificity wins": ticket, then agent frontmatter, on-demand skills, auto-loaded skills and `PROJECT_CONTEXT.md`, folder `README.md`, then `CLAUDE.md`, memory and glossary | No source-authority order between evidence sources yet (OP-06). Conflicts are kept as contradictions and never averaged (spec §10.5) |
| Traceability | Which channels were active at spawn | Locator, source version and hash per evidence item. Template id, version and input fingerprint per Jev call. One Langfuse trace per run |
| Learning | `route-learning` and `capture-learning` write to `PROJECT_CONTEXT.md`, memory files, docs and ADRs, and later agents receive them through the same channels | Live: a decision a human approved is staged, published to Git by a person and offered to later decisions as precedent. Planned: a learning evaluator distils Langfuse outcomes into Neo4j aggregates that routing reads. Process changes only through reviewed promotion |

**Where the two meet in V0.** The kernel's host LLM is a Claude Code session. The legacy
channels (`CLAUDE.md`, auto-memory, skills, MCP) therefore still reach it during host work, next
to the kernel's packet. The kernel neither controls nor records them; the `/leafcutter` skill
pre-approves only `run`, `resume` and `status` (design part 5). The spec calls Claude Code hosting "a bootstrap
compromise, not a sandbox or a guaranteed clean model context" (spec §2.3, §11.5). A clean
per-task context comes with direct executors in Stage 5 (spec §20). See OP-12.

Open points for this page: OP-06, OP-11, OP-12, OP-13, OP-29, OP-31 in [open points](c3-022-decision-kernel-flows-open-points.md).

## Legend

| Element | Meaning |
|---|---|
| Solid arrow | A context path live on main |
| Dotted arrow | A planned context path |
| Cylinder | Stored data: registry, configuration, repository files, records, database |
| Box inside "Assembled by kernel code" | Deterministic code that selects and shapes context |

## Cross-Links

- Parent: [Design Map](c2-007-decision-kernel-flows-overview.md)
- Detail pages: [Jev calls](c3-017-decision-kernel-context-jev.md), [Research](c3-018-decision-kernel-context-research.md),
  [Host, worker, human](c3-019-decision-kernel-context-host-worker-human.md)
- Memory: [Colony Memory — Container Overview](../components/colony-memory.md),
  [Learning loop](c3-020-decision-kernel-flows-learning-loop.md)
- Legacy: [Agent Knowledge Plane](../agent_knowledge_plane.md),
  [Agent Knowledge System](../agent_knowledge_system.md),
  [Injection Builder](../components/injection-builder.md)
- Later-stage context: [spec §17](../../analysis/2026-09-30-leafcutter-kernel-spec-rev3-7-later-stages.md)
