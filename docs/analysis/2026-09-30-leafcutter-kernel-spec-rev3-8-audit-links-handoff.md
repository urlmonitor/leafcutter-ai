---
title: "Leafcutter Kernel Specification Rev 3 - Part 8 of 8"
description: "In-tree copy of the Revision 3 Leafcutter decision-kernel specification (30 September 2026), part 8 of 8: coverage audit, verified links and coding-agent handoff (Part D, sections 22-24). Text is verbatim; only cross-part anchor links were rewritten."
type: reference
status: active
created: 2026-09-30
last_updated: 2026-09-30
components:
  - decision_kernel
---

> Source-of-truth specification for TICKET-20260930-KernelBootstrapV0, copied from the workspace file `leafcutter_kernel_bootstrap_specification.md`. Part 8 of 8 ([previous part](2026-09-30-leafcutter-kernel-spec-rev3-7-later-stages.md) | last part). Split only to satisfy the 300-line doc limit.

# Part D — Coverage audit, research links, and handoff

## 22. Coverage of the discussion [AUDIT]

This table makes explicit where each substantial idea belongs. Being included in the design does not make a later-stage item an MVP build requirement.

| Discussed idea | Specification location | Stage |
|---|---|---|
| Tiny kernel: Jev decisions plus deterministic dispatcher | 5, 8, 9 | MVP |
| LangGraph as the fixed orchestration runtime | 2, 5, 8 | MVP |
| Common Task, Request, Evidence, Decision, and Result contracts | 7 | MVP |
| Parent-child requests, granular graphs, and resumable continuations | 7, 8 | MVP |
| Reuse Leafcutter's existing capability registry | 2, 6 | MVP |
| No suitable graph creates a Leafcutter capability-gap record | 6, 14 | MVP |
| Generic evidence categories rather than hard-coded framework names | 5, 10 | MVP |
| Jev chooses bounded next actions; Claude supplies options/questions/synthesis | 9–11 | MVP |
| Missing knowledge triggers research rather than guessing | 9, 10 | MVP |
| Parallel researchers and independent requests | 8, 10, 17, 18 | MVP foundation; expanded later |
| Claude Code slash-command frontend, no new UI | 11 | MVP |
| Host fallback until native capabilities are worth extracting | 11, 14 | MVP |
| Langfuse tracing and MCP inspection from the beginning | 12 | MVP |
| Transparent decisions, evidence, metrics, versions, and approvals | 7, 9, 12 | MVP |
| Confidence distinct from completeness and authorization | 9, 18 | MVP foundation; engineering gate later |
| Existing ADR reuse and missing decision-basis research | 10, 19 | MVP research; formal learning later |
| Python versus JSON/YAML workflow representation | 15, 21 | MVP dogfooding research |
| Glossary and components as a shared semantic model | 17 | Stage 2 |
| Knowledge graph linking functions, ACs, tests, docs, and diagrams | 17 | Stage 2 |
| Names → docstrings → implementation progressive retrieval | 17 | Stage 2 |
| Exact search, structural search, BM25, vectors, and Jev reranking | 17 | Stage 2 |
| Small-model keyword expansion for vocabulary gaps | 17 | Stage 2 |
| One information-need search capability for the coding agent | 17 | Stage 2 |
| Existing read location versus intended write location | 17 | Stage 2 |
| Reusable successful searches and query/plan memory | 17, 19 | Stages 2/4 |
| Context discovery before acceptance criteria | 18 | Stage 3 |
| AC-specific context and implementation readiness | 18 | Stage 3 |
| Dynamic model prompts and role-specific contracts | 18 | Stage 3 |
| Folder/component checklists as executable policies | 18 | Stage 3 |
| Context, decision, and post-implementation verification rules | 18 | Stage 3 |
| Policy inheritance, conditional scope, and mandatory gates | 18 | Stage 3 |
| Documentation and architecture diagram impact | 18 | Stage 3 |
| Assess whether policies need updating, not compulsory edits | 18, 19 | Stages 3/4 |
| Bugs become reviewed policy/ADR lessons at the right scope | 19 | Stage 4 |
| Components getting too big: evidence-backed split proposals | 19 | Stage 4 |
| Learn from patches without treating changed files as perfect labels | 17, 19 | Stages 2/4 |
| Direct SDK/model gateway and multiple specialist providers | 20 | Stage 5 |
| Codex, VS Code, web, issue-tracker, and CI clients | 20 | Stage 5 |
| Smaller context and more targeted compute improve economics | 1, 16, 19 | Measure throughout; not guaranteed |
| Text-only Jev cannot independently verify image contents | 9.6 | Explicit boundary |

### 22.1 Material refinements over the earlier V0 specification

The earlier description left the broader target and the first deliverable insufficiently separated. This revision adds explicit stages and a stop line.

It also makes previously implicit implementation mechanics explicit: canonical status normalization, parent continuation, root completion, actual host handoff and resume, registry eligibility, structured human authority, source/version provenance, durable state distinct from tracing, and no-progress controls.

It avoids three unsafe assumptions: that a confidence score establishes readiness, that a slash command supplies a callback API into the host model, and that a classifier can generate or approve the runtime's own policies or capabilities.

## 23. Verified research and implementation links [REFERENCE]

These links were opened and checked on **30 September 2026**. They are implementation references, not a guarantee that the newest release will remain compatible. Pin dependencies and verify the exact API in the repository being built.

### 23.1 Jev, LangChain, and the concrete LangGraph implementation — start here

#### J1. Official TypeSafe integration documentation

<https://docs.langchain.com/oss/python/integrations/providers/typesafe>

Primary adapter reference: `TypeSafeClassifier`, state-plus-questions invocation, answer types, and the current Python integration shape. Use this instead of relying on abbreviated earlier conversation examples.

#### J2. Building a Harness with Jev

<https://www.langchain.com/blog/building-a-harness-with-jev>

LangChain article, **17 September 2026**. The previously discussed introduction to typed decisions, multiple independent classifications on shared state, and complementary generative-model use. Performance and cost statements are contextual, not Leafcutter commitments.

#### J3. Building Production Agents with Jev and LangGraph

<https://www.langchain.com/blog/building-prod-with-jev-and-langgraph>

LangChain article, **25 September 2026**. The previously discussed architecture reference: Jev supplies structured judgments while LangGraph owns control flow, state, escalation, and composition.

#### J4. Concrete LangGraph implementation linked by the article

<https://gist.github.com/sydney-runkle/a632ba4ea0b2b72501dfa4b6ab2a7d8a>

Sydney Runkle's document-review example. It contains typed classification, code-based routing, human-in-the-loop escalation, parallel examples, and deterministic tests. Inspect particularly `review.py` and `test_review.py`.

Use its classifier/node/routing and testing patterns as reference. The gist includes multiple classifier/provider configurations and LangSmith-oriented tracing examples. Do not copy provider assumptions, tracing setup, or memory-only persistence into Leafcutter without adaptation. **Leafcutter uses Langfuse and durable MVP state.**

#### J5. Official package source and release metadata

Source README:

<https://raw.githubusercontent.com/langchain-ai/langchain/master/libs/partners/typesafe/README.md>

Package listing:

<https://pypi.org/project/langchain-typesafe/>

The inspected listing showed **0.0.1a3**, released **20 September 2026**, as a pre-release. Pin a compatible version and add a contract smoke test. Upstream `master` may change after this document's verification date.

#### J6. Confidence semantics

<https://docs.typesafe.ai/confidence>

Authoritative explanation of probability distributions versus the derived confidence field. Essential for avoiding a misleading global readiness score.

#### J7. Models, input limits, and versioning

<https://docs.typesafe.ai/models>

Model identities, aliases, text-only input, request limits, and pricing metadata. Record the returned model version rather than relying on an unversioned moving alias. Recheck limits and prices at implementation time.

#### J8. Question primitives and independence

<https://docs.typesafe.ai/primitives>

Guidance on atomic questions and independently evaluated questions sharing state. Useful for deciding which judgments can be batched and which need another step.

### 23.2 LangGraph orchestration primitives

#### G1. LangGraph Graph API

<https://docs.langchain.com/oss/python/langgraph/graph-api>

State, nodes, routing, `Send`, and `Command`. Foundation for a fixed kernel with dynamically scheduled work.

#### G2. Subgraphs and state mapping

<https://docs.langchain.com/oss/python/langgraph/use-subgraphs>

Composition of small graphs, shared versus transformed state, and subgraph integration. Useful for avoiding unnecessary coupling between capability internals.

#### G3. Persistence and checkpoints

<https://docs.langchain.com/oss/python/langgraph/persistence>

Durable execution state and thread identity. Use a real compatible persistence path for resumed MVP runs.

#### G4. Interrupts and resume

<https://docs.langchain.com/oss/python/langgraph/interrupts>

Persistent interruption and resumption behavior. Review replay/idempotency requirements when placing work before an interrupt.

### 23.3 Langfuse and Claude Code

#### L1. LangChain and LangGraph instrumentation

<https://langfuse.com/integrations/frameworks/langchain>

Callback integration, custom observation/trace behavior, and current SDK guidance.

#### L2. LangGraph cookbook

<https://langfuse.com/integrations/frameworks/langgraph>

Examples for graph tracing, metadata, nested traces, and correlation. Adapt examples to the pinned SDK and Leafcutter's process-resume boundary.

#### L3. Langfuse data MCP

<https://langfuse.com/docs/api-and-data-platform/features/mcp-server>

Authenticated project-data access. Configure the client for read-only inspection of the MVP demonstration. This is separate from runtime telemetry ingestion and from the public documentation MCP.

#### C1. Claude Code skills

<https://code.claude.com/docs/en/skills>

Project skills, slash invocation, script support, and invocation controls. Basis for the thin `/leafcutter` transport client, not a kernel implementation.

### 23.4 Earlier retrieval research retained for Stage 2

These are author-maintained projects, not mandatory dependencies or verified Leafcutter integrations. Treat their benchmarks as project-specific experiments.

#### R1. Jevgrep

<https://github.com/dzhng/jevgrep>

Hierarchical repository, file, declaration, and excerpt retrieval exposed to coding agents as a CLI/skill. Relevant to progressive code-context discovery.

#### R2. Claude Code Jev plugin

<https://github.com/BorisLeMeec/jev>

Claude Code plugin and semantic navigation/read filtering. Relevant to reducing unnecessary source context and examining hook-based integration patterns.

#### R3. Hybrid retrieval CLI

<https://github.com/romeromarcelo/jev-retrieval>

Lexical candidate retrieval combined with Jev filtering/ranking. Useful as a comparison point, not a mandate to make lexical search the only recall path.

## 24. Ready-to-use coding-agent instruction [MVP HANDOFF]

> Implement **Stage 0 and Stage 1 MVP only** from this specification in the existing Leafcutter repository. Read Stages 2–5 to preserve the architectural extension points, but do not implement them now.
>
> First inspect and reuse the existing capability registry, glossary/component access, configuration, persistence, source access, and logging conventions. Do not create parallel abstractions merely to match the example directory names.
>
> Build the native LangGraph kernel, typed contracts, registry eligibility and Jev routing, generic decision/research capabilities, one real read-only source adapter, persistent work-item continuations, validated human/host resume, bounded Claude Code fallback, capability-gap records, runtime safeguards, and Langfuse observability.
>
> Use the verified links in Section 23—especially the official TypeSafe adapter documentation and the concrete Jev/LangGraph implementation—while checking the pinned package APIs. Use Langfuse rather than copying LangSmith-specific setup from the example.
>
> The first usable product is a **resumable evidence-backed decision assistant through `/leafcutter`**, not an autonomous coding platform. It must perform real native routing, evidence retrieval, and continuation rather than outsourcing the workflow to a Claude prompt.
>
> Deliver working code, schemas, tests, setup instructions, the project skill, a sample decision/research report, an inspectable live trace, and explicit remaining limitations. Use the first research loop to investigate longer-term workflow representation only after the minimal runtime works. Do not auto-approve its recommendation or execute generated workflow code.

---

**Central invariant:** Leafcutter owns the allowed engineering process. Jev evaluates bounded questions. Generative models perform explicitly requested work. Evidence, deterministic gates, and authorized approvals determine whether the workflow may proceed.
