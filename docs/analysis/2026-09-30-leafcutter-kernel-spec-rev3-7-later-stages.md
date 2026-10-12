---
title: "Leafcutter Kernel Specification Rev 3 - Part 7 of 8"
description: "In-tree copy of the Revision 3 Leafcutter decision-kernel specification (30 September 2026), part 7 of 8: later stages 2-5 and open architectural decisions (Part C, sections 17-21). Text is verbatim; only cross-part anchor links were rewritten."
type: reference
status: active
created: 2026-09-30
last_updated: 2026-09-30
components:
  - decision_kernel
---

> Source-of-truth specification for TICKET-20260930-KernelBootstrapV0, copied from the workspace file `leafcutter_kernel_bootstrap_specification.md`. Part 7 of 8 ([previous part](2026-09-30-leafcutter-kernel-spec-rev3-6-gaps-build-verification.md) | [next part](2026-09-30-leafcutter-kernel-spec-rev3-8-audit-links-handoff.md)). Split only to satisfy the 300-line doc limit.

# Part C — Later stages: preserve the vision, do not implement now

## 17. Knowledge, retrieval, and context compilation [STAGE 2]

### 17.1 Start with the existing glossary and components

Use the glossary as canonical terminology and the component directory as a first classification map. Select relevant glossary terms and compact component descriptors before deeper retrieval. Do not inject the entire catalog once it becomes too large.

A component is a primary join point connecting code, functions/classes, acceptance criteria, tests, documentation, diagrams, ownership, and history. Relationships may be many-to-many: do not assume one file belongs to exactly one concern or that every acceptance criterion has only one component.

The shared terminology should be available to routing, research, coding, testing, and documentation views. Unknown vocabulary may become a proposal for review, not an automatically created canonical concept.

### 17.2 Progressive disclosure and knowledge-graph traversal

The graph is an index to query, not a giant context payload.

```text
Component / architecture overview
    |
Relevant modules and folders
    |
Function/class names and signatures
    |
Selected docstrings, types, and imports
    |
Callers, callees, interfaces, tests, linked ACs and ADRs
    |
Selected source implementation excerpts
    |
Full file or wider neighborhood only when justified
```

Jev evaluates relevance and whether the available resolution is sufficient for the current question. It may request docstrings after names, or source after docstrings. The code controls retrieval and budgets.

Stopping after names may be sufficient to locate a likely function; it is generally not sufficient to establish that its implementation satisfies a behavioral requirement.

Possible graph entities include `Repository`, `Component`, `Folder`, `File`, `Function`, `Class`, `Interface`, `Type`, `API`, `Test`, `AcceptanceCriterion`, `Ticket`, `ADR`, `Document`, `Diagram`, `Concept`, and `PolicyRule`.

Useful relationships include containment, declaration, calls, imports, implementation, tests, documentation, dependencies, and historical changes. Store extraction method, version, and provenance on relations. Inferred or incomplete call graphs—especially for dynamic behavior—must not masquerade as exact facts.

### 17.3 Hybrid search rather than replacing exact search

Expose one information-need interface to the calling agent:

```text
Find the retrieval engine that selects relevant documents before generation.
```

The internal engine can choose exact symbol/path lookup, grep, structural search, graph traversal, BM25, embeddings, or Jev reranking. It can run independent strategies concurrently or fall through after a failed or irrelevant result.

When “retrieval engine” does not appear in the repository, a small generative operation may propose likely synonyms or identifiers. Jev evaluates candidates; deterministic tools execute searches.

Do not make BM25 a mandatory gate before every semantic search. A vocabulary mismatch can remove the right candidate before the reranker sees it. Maintain alternate recall paths and measure both recall and precision.

Keep exact search and direct reads available. A Jev filter is not proof that every discarded file is irrelevant. Preserve uncertain candidates as reading leads where appropriate. Prior researched examples are linked in [R1](2026-09-30-leafcutter-kernel-spec-rev3-8-audit-links-handoff.md#r1-jevgrep), [R2](2026-09-30-leafcutter-kernel-spec-rev3-8-audit-links-handoff.md#r2-claude-code-jev-plugin), and [R3](2026-09-30-leafcutter-kernel-spec-rev3-8-audit-links-handoff.md#r3-hybrid-retrieval-cli).

### 17.4 Read location versus write location

Distinguish:

- Where relevant behavior currently exists.
- Where new behavior should belong under the repository's approved architecture.

The highest-ranked existing file is not automatically the right insertion point. Write-location recommendations need principles, component boundaries, interfaces, and existing patterns—not relevance alone.

Continue retrieving related tests, callers, schemas, and constraints after identifying a likely implementation file. Avoid prematurely narrowing the model's context to a misleading single function.

### 17.5 Context bundles and reusable search memory

Compile an immutable/versioned `ContextBundle` containing task intent, glossary/component references, selected evidence, ACs/decisions where available, constraints, unresolved contradictions, likely read/write locations, related tests/interfaces, and explicit omissions.

Generate role-specific views rather than repeatedly sending the full bundle to every model. Context compilation is selection and organization, not an authority to change the original request.

Store successful searches, concept-to-symbol mappings, and reusable retrieval plans as candidates for reuse. Revalidate against repository changes, relevant source versions, permissions, model/policy versions, and corrected evidence.

Files changed in a patch are useful feedback but not perfect relevance labels: unchanged interfaces, tests, and architectural constraints may have been essential context.

**Stage 2 exit:** the same kernel can supply a compact evidence package before a reasoning/coding model is called, using both structural and semantic retrieval where justified.

## 18. Engineering workflows and executable component policies [STAGE 3]

### 18.1 Two discovery phases

**Before acceptance criteria:** a feature idea triggers relevant discovery of architecture, existing behavior, related requirements, APIs, constraints, and previous decisions. The system finds answers before asking the user questions the repository could answer.

Parallel researchers can inspect architecture, code, tests, documentation, and history. These are capabilities composed of deterministic tools, Jev judgments, and selective synthesis—not necessarily a full generative agent per branch.

The requirements model receives a prepared evidence package and genuine unresolved product questions. It can then formulate acceptance criteria using that evidence.

**After acceptance criteria:** map each AC to relevant components, symbols, interfaces, tests, documents, and decisions. Determine impact and prepare the implementation contract. The first discovery pass does not replace this finer-grained pass.

Both phases use the same kernel and typed contracts.

### 18.2 Readiness is an explicit gate

Track architecture, security/privacy, data changes, API compatibility, reliability, documentation, tests, and product questions individually. An engineering concern can be satisfied, not applicable with a reason, unresolved, or blocked.

```text
READY TO IMPLEMENT requires:
  all mandatory decisions resolved
  all required approvals recorded
  all required evidence current and accessible
  no unresolved blocking contradiction or product question
  a valid implementation contract for the actual affected scope
```

A classifier confidence score cannot bypass these requirements. A displayed completeness percentage is only a summary of tracked concerns, not a claim that all possible bugs or unknowns have been eliminated.

### 18.3 One implementation contract, different model views

Create a shared contract with the goal, ACs, approved decisions, constraints, implementation locations, relevant source, dependencies, required tests, artifact obligations, and unresolved limitations.

Compile:

- **Coding view:** intended behavior, decisions, architecture constraints, relevant code, permitted change scope.
- **Testing view:** AC-to-test mapping, invariants, negative cases, concurrency/failure scenarios, observable behavior, and affected interfaces.
- **Documentation view:** changed behavior, evidence of documentation/diagram impact, relevant sections, and required consistency updates.

The testing model must not simply mirror the coding model's claimed implementation. Execute tests and inspect independently relevant evidence. Documentation should change when behavior or architecture changes, not automatically because its filename looks related.

### 18.4 Component-scoped executable engineering policies

Attach policies to repository, language/framework, component, and folder scopes. Local policy files may reference stable policy IDs rather than duplicating a full inherited rule set in every directory.

Three rule types execute at different stages:

| Type | Role |
|---|---|
| Context rule | Require relevant evidence before planning or execution |
| Decision rule | Require an explicit criterion-based choice, research request, or approval |
| Verification rule | Check implemented behavior/artifacts against the agreed contract |

A fourth maintenance assessment asks whether the change exposed a missing or stale rule. It does **not** require modifying a checklist after every change.

Illustrative future policy data:

```json
{
  "id": "LG-PARALLEL-001",
  "version": "1.0",
  "scope": {"component_ids": ["langgraph"]},
  "stages": ["planning", "review"],
  "applicability_question": "Does this change introduce parallel work?",
  "evidence_needs": ["task_context", "internal_principles", "existing_patterns"],
  "on_applicable": [
    "require_state_merge_decision",
    "require_timeout_and_partial_failure_decision",
    "require_parallel_behavior_tests"
  ],
  "verification": [
    "inspect_state_merge_implementation",
    "execute_required_tests"
  ],
  "maintenance": {
    "assess_new_recurring_concerns": true,
    "approval_required_for_policy_change": true
  }
}
```

Action names resolve only to trusted registered behavior. They are not arbitrary executable strings.

### 18.5 Inheritance, conflict handling, and scope expansion

Compose applicable global, language/framework, component, and folder policies. More specific rules may add requirements; they may weaken a broader mandatory rule only through an explicitly authorized override mechanism.

Conflicting rules produce a conflict decision, not a model-selected winner without explanation.

Compile policies before implementation and again against the actual changed-file/symbol set. If the scope expands to a new component, retrieve its policies and re-evaluate the contract before accepting the change.

Use deterministic structural checks and tests wherever possible. Semantic checks can assess applicability and explanatory consistency, but they are not proof of all behavior.

**Stage 3 exit:** a real feature follows discovery, approved decisions, role-specific contracts, implementation, tests, and documentation/architecture impact review with a complete evidence trail.

## 19. Controlled learning and organizational memory [STAGE 4]

### 19.1 Research becomes reusable decision knowledge

When no internal decision basis exists, research gathers relevant authority, patterns, alternatives, constraints, and task facts. A generative capability synthesizes candidate criteria and a proposed decision basis.

An ADR records alternatives, chosen approach, assumptions, consequences, scope, evidence versions, owner, approval, and review triggers. It is reusable knowledge—not permanent truth.

Framework upgrades, new constraints, incidents, or conflicting evidence may require reassessment. Do not encode “we will never need to research this again” as a runtime assumption.

### 19.2 Bugs feed reviewed policy proposals

After root-cause analysis, ask whether the problem came from:

```text
missing knowledge
an incorrect decision
an existing rule that was not followed
an inadequate verification check
a stale source or wrong scope
a gap outside the currently defined engineering process
```

A template or generative capability drafts the lesson. Jev can classify candidate scope and relevance against an existing catalog.

Propose the narrowest useful scope: local function, component, framework/language, repository, or organization. Include the incident evidence, relevant failed decision trace, candidate rule/ADR change, expected benefit, false-positive risk, and evaluation cases.

Require review before activating a changed policy. Preserve previous versions and a rollback path. A new rule reduces a known failure mode; it does not guarantee that the whole bug class can never recur.

### 19.3 Component health and potential splits

Use measurable signals: responsibility clusters, dependency density, co-change patterns, AC groupings, ownership friction, retrieval ambiguity, and maintenance burden.

Jev may assess whether candidate boundaries are coherent. A generative/architectural review develops options. Function count alone is not a reason to split a component.

A graph may propose an architecture change; it must not silently refactor the repository or remap approved policies/ACs. Preserve migration history and approved ownership boundaries.

### 19.4 Evaluate before activation

Evaluate proposed policies, capability changes, retrieval plans, and prompt/model versions on held-out cases. Measure missed relevant evidence, unnecessary blockers, false positives, fallback burden, downstream correctness, and observed cost/latency.

Updating a knowledge graph or policy catalog is organizational learning. It does not imply the Jev model weights automatically train themselves from Leafcutter traces.

**Stage 4 exit:** a reviewed lesson demonstrably changes future work while retaining its evidence, evaluation, version, and rollback controls.

## 20. Independent clients and specialist executors [STAGE 5]

Replace cooperative host fallback with explicit model/agent executors when justified. Distinguish:

- A direct text-model invocation for synthesis or question generation.
- A coding agent that needs tools, a workspace, permissions, and execution control.

These are different executor capabilities, not interchangeable API calls.

Provider-specific integration remains behind the same invocation/result contracts. Stronger isolation can supply fresh per-task context and controlled tools without rewriting the engineering process.

Add Codex, VS Code, a web UI, issue-tracker integration, or CI only after the client-independent API is stable. Every client must preserve pending interaction IDs, approvals, evidence references, and resume semantics.

Multi-user authorization, quotas, tenancy isolation, deployment operations, and production-grade task scheduling are later-stage concerns.

**Final target achieved:** Leafcutter receives an engineering intent, acquires relevant context, resolves or explicitly records decisions, invokes specialist executors only when appropriate, verifies outputs, and preserves reviewed organizational knowledge—without depending on a particular chat interface or coding-model vendor.

## 21. Architectural decisions still to make [STAGED]

| Decision | When and boundary |
|---|---|
| Exact existing registry and persistence interfaces | Stage 0 inspection; do not invent replacements |
| Workflow representation: Python, declarative, or hybrid | First dogfooding research after the MVP loop runs; LangGraph remains fixed |
| Durable local checkpointer and artifact layout | Stage 0/1; choose the smallest compatible existing option |
| Source authority and conflict precedence | Configure minimal explicit rules for MVP; extend governance in later stages |
| Knowledge-graph storage and extraction | Stage 2; Neo4j versus relational graph structures is not pre-decided |
| Retrieval strategies, caching, and invalidation | Stage 2, guided by measurements rather than mandatory embeddings |
| Policy inheritance, authority, and approval | Stage 3/4 before automated policy application or mutation |
| Native generative/coding executors | Stage 5 or a justified incremental replacement for observed host reliance |
| Risk thresholds and calibration | Begin evaluation in MVP and revisit per workload/model/version |

Do not turn the bootstrap into an unbounded exercise in researching its own prerequisites. Record provisional, reviewable implementation choices where necessary to get the first narrow loop running.
