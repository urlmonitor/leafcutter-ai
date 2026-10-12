---
title: "Leafcutter Kernel Specification Rev 3 - Part 1 of 8"
description: "In-tree copy of the Revision 3 Leafcutter decision-kernel specification (30 September 2026), part 1 of 8: goal, settled decisions, stages and exact MVP boundary (Part A, sections 1-4). Text is verbatim; only cross-part anchor links were rewritten."
type: reference
status: active
created: 2026-09-30
last_updated: 2026-09-30
components:
  - decision_kernel
---

> Source-of-truth specification for TICKET-20260930-KernelBootstrapV0, copied from the workspace file `leafcutter_kernel_bootstrap_specification.md`. Part 1 of 8 (first part | [next part](2026-09-30-leafcutter-kernel-spec-rev3-2-runtime-and-registry.md)). Split only to satisfy the 300-line doc limit.

# Leafcutter: Decision Kernel and Engineering Runtime

**Revised implementation specification · Revision 3 · 30 September 2026**  
**Implementation target now: Stage 0 and Stage 1 MVP only**  
**Fixed foundations: LangGraph runtime, Jev decision adapter, existing Leafcutter capability registry, Langfuse observability, Claude Code as the first client**

> Build a small, real, resumable decision-and-research kernel first. Preserve the larger engineering-runtime architecture, but do not implement the later stages in the MVP.

This document consolidates the discussion, separates the final product goal from the first deliverable, defines the contracts between small capabilities, and supplies implementation references—including the existing Jev/LangGraph implementation. It replaces the earlier V0 specification. It is a specification, not a claim that the repository or integrations have already been implemented or tested.

The words **must**, **should**, and **may** describe requirements for the stage named in the section. A requirement under a later stage is not an MVP requirement. Example policies, tickets, function names, and repository layouts are illustrative, not assertions about the current Leafcutter repository.

## Reading guide

| Part | Sections | Purpose |
|---|---|---|
| A | 1–4 | Final goal, settled decisions, development stages, exact MVP boundary |
| B | 5–16 | MVP architecture, common contracts, scheduling, Jev, Claude Code, Langfuse, safeguards, implementation and testing |
| C | 17–21 | Later-stage retrieval, engineering policies, learning, independent clients, outstanding ADRs |
| D | 22–24 | Coverage audit, verified implementation links, coding-agent handoff |

---

# Part A — Final goal, stages, and MVP boundary

## 1. Purpose and final goal [TARGET]

### 1.1 What Leafcutter should become

Leafcutter should become an **evidence-driven engineering runtime**, not another large prompt wrapped around a coding model.

A user supplies an information need, an architectural question, a feature idea, or a bug. Leafcutter owns the process of discovering relevant information, identifying unresolved questions, applying engineering policies, researching missing decision bases, requesting human choices, and preparing the appropriate work for specialist models.

The expensive generative model should not have to rediscover the repository, terminology, architecture, engineering process, and relevant constraints from scratch on every task.

The final system combines two persistent models:

- **System knowledge:** glossary, components, functions, classes, interfaces, APIs, types, tests, requirements, acceptance criteria, documentation, diagrams, dependencies, and history.
- **Engineering knowledge:** principles, approved ADRs, scoped policies, decision criteria, required evidence, implementation obligations, verification requirements, and approved lessons.

These models support a shared process:

```text
User intent / feature / bug / decision / information need
    |
    v
Interpret intent and select a registered capability
    |
    v
Acquire relevant evidence; identify missing knowledge or decisions
    |
    +--> retrieve from available sources
    +--> conduct bounded research
    +--> generate options or synthesize findings when necessary
    +--> ask humans for requirements, preferences, or approval
    |
    v
Record supported decisions and unresolved limitations
    |
    v
Compile a task-specific implementation contract
    |
    +--> coding view --> coding model
    +--> testing view --> test-writing model
    +--> documentation view --> documentation model
    |
    v
Verify behavior, policy obligations, tests, and artifact impact
    |
    v
Record outcomes; propose reviewed updates to knowledge and policies
```

This is a **bounded, resumable work system**, not an unlimited self-running agent or literal perpetual-motion machine.

### 1.2 Division of responsibility

| Layer | Responsibility |
|---|---|
| Leafcutter / LangGraph | Own workflow state, dispatch, continuation, permissions, budgets, mandatory gates, and completion |
| Jev | Evaluate bounded questions about relevance, applicability, candidate choices, sufficiency, and routing |
| Deterministic tools | Exact search, graph queries, schema validation, arithmetic, structural checks, test execution, and durable bookkeeping |
| Generative models | Formulate questions, generate options, synthesize evidence, analyze genuinely open-ended trade-offs, and produce code or documents |
| Humans | Supply preferences and missing requirements; approve consequential choices and policy changes where required |
| Langfuse | Make execution, evidence requests, decisions, costs where available, and outcomes inspectable |

**Jev is the decision component, not the scheduler, execution engine, authorization authority, or proof of correctness.**

### 1.3 Benefits to test, not assume

The architecture aims to reduce exploratory model turns and repeated irrelevant context, improve coverage of engineering concerns, and make decisions explainable through explicit evidence and criteria.

It should also make additional parallel research economically practical. However, greater accuracy, lower total cost, lower latency, and the ability to use smaller coding models are **hypotheses to measure**. They are not guaranteed by introducing Jev, a knowledge graph, or additional classifier calls.

## 2. Settled decisions and important boundaries [ALL STAGES]

### 2.1 Settled decisions

1. **LangGraph implements the kernel and reusable multi-step capabilities.** Do not reopen the choice of orchestration framework.
2. **Jev is the default bounded semantic decision provider.** Access it through a narrow adapter; do not spread provider-specific response handling throughout the graphs.
3. **Reuse the existing Leafcutter capability registry.** Normalize its descriptors through an adapter rather than creating a competing registry.
4. **Langfuse is included from the beginning.** Runtime instrumentation and a documented MCP inspection setup belong in Stage 1.
5. **Claude Code is the initial interaction surface.** Start with a project skill exposed as `/leafcutter`; do not build a new UI.
6. **The core remains client-independent.** The same application API must be callable from a CLI, another Python application, a future MCP tool, or later clients.
7. **Small capabilities communicate through typed contracts and the kernel.** They do not discover and invoke arbitrary peer capabilities on their own.

### 2.2 Existing Leafcutter assets

The discussion establishes that Leafcutter already has a **capability registry, glossary, and component directory**. These are user-provided facts, not the result of repository inspection during preparation of this specification.

Stage 0 must locate their actual representations, schemas, APIs, and conventions. Other assets—ADRs, search indexes, model gateways, persistence facilities, source catalogs, and graph storage—must be discovered rather than assumed to exist.

### 2.3 Corrections to avoid carrying earlier shorthand into code

- A classifier cannot generate arbitrary questions, explanations, keywords, missing capabilities, or new policies. It can select among supplied candidates. Templates, deterministic rules, or a generative capability construct new text and options.
- Jev's `confidence` is not the same field as a winning option's probability, and neither is proof that all relevant information is present. See [J6](2026-09-30-leafcutter-kernel-spec-rev3-8-audit-links-handoff.md#j6-confidence-semantics).
- A semantic assessment may identify a missing requirement; it must not silently invent the user's preference.
- “All checks ran” means execution coverage, not that every check was correct. Tests, structural validators, evidence quality, and human approval remain necessary.
- Repo files, web pages, source descriptions, and model outputs are evidence, not instructions authorized to alter permissions or override policies.
- A graph may contain ordinary Python nodes. Do not manufacture a subgraph for every single classifier call merely to make the catalog look uniform.
- The runtime may propose a new capability or policy. It must not activate or execute newly generated code automatically.
- Claude Code hosting is a bootstrap compromise, not a sandbox or a guaranteed clean model context. Stronger isolation and direct model invocation are later-stage executor concerns.

## 3. Development stages [ROADMAP]

These are capability increments, not separate replacement systems. Each stage extends the same registry, contracts, state model, and observability foundation.

| Stage | What is built | Exit condition |
|---|---|---|
| **0 — Preparation** | Repository mapping, compatibility checks, credential setup, provisional bootstrap choices | The implementation reuses the right existing interfaces and identifies remaining unknowns |
| **1 — MVP: bootstrap decision kernel** | Native LangGraph kernel; Jev routing and decisions; a generic research loop; real read-only retrieval; Claude Code handoff; persistent resume; capability gaps; Langfuse | A real question is researched when necessary, returned with evidence, and traceable end to end without hidden host-side orchestration |
| **2 — Knowledge and context compiler** | Glossary/component-aware search, progressive disclosure, graph-backed retrieval, hybrid code search, reusable retrieval memory | Relevant evidence is assembled before a specialist model is called, without exposing the entire repository |
| **3 — Engineering workflows and executable policies** | Discovery before acceptance criteria; AC-specific context; inherited component policies; role-specific contracts; post-change verification | A feature passes explicit readiness gates and receives coding, testing, and documentation views of the same contract |
| **4 — Controlled learning** | Research-to-ADR reuse; bug-to-policy proposals; capability prioritization; component-boundary analysis | Reviewed lessons change future behavior, with provenance, evaluation, versioning, and rollback |
| **5 — Independent engineering runtime** | Direct model/agent executors, additional clients, stronger isolation, production operational controls | The backend works without Claude Code as its host and can use specialist providers without changing the engineering process |

**Only Stage 0 and Stage 1 are authorized by the MVP build instruction.** Later-stage extensibility is required at the contracts, registry, and execution boundaries; later-stage implementations are not.

## 4. Exact MVP: what to build now [STAGE 1]

### 4.1 Product definition

The MVP is a **read-oriented, evidence-backed decision assistant inside Claude Code**.

It accepts a free-form goal through `/leafcutter`, identifies a supported decision/research capability, gathers relevant evidence, asks for generative work or human input when necessary, and returns a structured result with supporting evidence, unresolved limitations, and trace references.

A future feature request may be classified or recorded as a missing capability. It must not silently trigger an unimplemented “build feature” workflow or start editing application code.

### 4.2 Minimum included functionality

| Area | Required MVP implementation |
|---|---|
| Kernel | Fixed LangGraph scheduler with typed work items, routing, dispatch, result validation, parent continuation, and terminal-state checks |
| Decision provider | Live Jev adapter plus deterministic test doubles |
| Registry | Adapter over the existing Leafcutter registry; eligibility filtering before semantic routing |
| Decisions | Supplied options and criteria, explicit missing-evidence/options/synthesis/human states, evidence-linked recommendations |
| Research | One domain-agnostic evidence-planning and collection graph |
| Retrieval | At least one real read-only repository/document adapter; reuse existing Leafcutter retrieval facilities |
| Generative work | Structured Claude Code handoffs for synthesis, options, question formulation, and bounded missing research |
| Human interaction | Durable pending question, validated response, explicit actor, and resume without restarting the task |
| Persistence | Durable checkpoints/work records and artifact references; no memory-only production path |
| Parallelism | At least two independent native evidence requests can execute concurrently and merge deterministically |
| Gap recording | Deduplicated capability-gap records and local backlog-ready artifacts; bounded fallback when permitted |
| Observability | Langfuse callbacks/custom observations, source/model/version metadata, explicit trace correlation across resume |
| MCP inspection | Document and smoke-test read-only inspection of a demonstration trace using the current Langfuse data MCP |
| Operational guards | Retry limits, active-time and call budgets, no-progress detection, cancellation, and idempotent resume |
| Deliverables | Implementation, schemas/fixtures, tests, configuration example, Claude Code skill, setup guide, sample decision report, trace evidence |

**Minimum native graphs:** `kernel`, `decision`, and `research`.

`route`, source adapters, result validation, gap recording, host handoff, and human interaction may be ordinary functions or nodes. They must implement the relevant contract but do not each need a separate subgraph.

### 4.3 Explicit exclusions

Do not build any of the following as part of the MVP:

- A new web frontend, editor extension, or custom chat interface.
- A full knowledge graph, embeddings pipeline, code parser platform, or enterprise semantic-search engine.
- Automatic feature implementation, application-code modification, deployment, or autonomous trading/external operations.
- An executable policy inheritance engine, automatic policy edits, or self-modifying graphs.
- Automatic ADR approval, component splitting, or architecture refactoring.
- A direct multi-provider model gateway solely to avoid using the agreed Claude Code bootstrap.
- A runtime compiler that executes JSON/YAML workflow definitions or generated Python.
- A replacement capability registry or a second logging/configuration framework.

MVP writes are limited to its own state, evidence snapshots, run artifacts, decision reports, and local capability-gap drafts in a configured run directory. External ticket publication or repository-policy changes require a later, explicitly authorized write capability.

### 4.4 Demonstration and stop line

Primary demonstration question:

> Should this new capability be an atomic operation/node or an encapsulated subworkflow/subgraph?

Run this against a small project context:

1. With an applicable existing decision basis, so research is not repeated needlessly.
2. Without sufficient decision knowledge, so evidence requests and bounded research are required.
3. With an unresolved user preference, so the run pauses and resumes.
4. With an unavailable capability, so the result records a gap rather than pretending to succeed.

The same generic flow must also handle a different question without graph-code changes, such as where a cache should live, using a different supplied context and criteria.

**Stop after this works end to end.** Deliver the later-stage roadmap and extension points, not a partial implementation of the entire final vision.
