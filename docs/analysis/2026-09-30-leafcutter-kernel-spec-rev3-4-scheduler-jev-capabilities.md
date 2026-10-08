---
title: "Leafcutter Kernel Specification Rev 3 - Part 4 of 8"
description: "In-tree copy of the Revision 3 Leafcutter decision-kernel specification (30 September 2026), part 4 of 8: scheduler, Jev adapter, decision and research capabilities (sections 8-10). Text is verbatim; only cross-part anchor links were rewritten."
type: reference
status: active
created: 2026-09-30
last_updated: 2026-09-30
components:
  - decision_kernel
---

> Source-of-truth specification for TICKET-20260930-KernelBootstrapV0, copied from the workspace file `leafcutter_kernel_bootstrap_specification.md`. Part 4 of 8 ([previous part](2026-09-30-leafcutter-kernel-spec-rev3-3-contracts.md) | [next part](2026-09-30-leafcutter-kernel-spec-rev3-5-client-observability-safeguards.md)). Split only to satisfy the 300-line doc limit.

## 8. Scheduler, recursion, and continuation [MVP]

The kernel is a fixed LangGraph whose **workload is dynamic**. Do not rebuild its topology for every question. Use dynamic dispatch and work-item data rather than generating executable graph definitions.

LangGraph provides state, nodes, conditional routing, `Send`, and `Command`; these are implementation primitives for the scheduler, not permission to execute model-generated code. See [G1](2026-09-30-leafcutter-kernel-spec-rev3-8-audit-links-handoff.md#g1-langgraph-graph-api).

### 8.1 Execution algorithm

1. Normalize `TaskInput`, persist initial evidence, and create a root request/work item with an explicit requested output.
2. Select runnable work whose dependencies are satisfied. Reserve budget and concurrency capacity before dispatch.
3. For new work, filter registry candidates, obtain a routing assessment where semantic selection is needed, and bind a validated capability ID/version.
4. For resumed work, reuse the existing capability binding and continuation; do not reinterpret it as a new root task.
5. Invoke the capability with isolated inputs. Parallel workers return results, not mutations of shared global state.
6. Validate its result schema, IDs, evidence references, proposed child requests, scope, and lifecycle invariants.
7. Atomically persist accepted results and update work-item state. Deduplicate equivalent evidence and requests.
8. If children or an external interaction are required, mark the parent `waiting` and record its continuation. It is no longer eligible for ordinary dispatch.
9. When required children finish, resume the owning capability with its previous continuation and the child results/new evidence references.
10. If a required child fails or blocks, propagate that state explicitly. The parent may request a bounded alternative; it must not claim complete evidence.
11. Finalize only when the root output contract is satisfied, no required work remains unresolved, and root-level gates permit completion.

Supporting evidence may be omitted when the budget is exhausted only if the result records that omission. Required evidence cannot silently become supporting evidence because a model prefers to finish.

### 8.2 Recursion means a work dependency graph, not recursive Python calls

A research capability can request source retrieval. That retrieval may request query expansion. The parent remains paused while the kernel schedules those requests.

```text
Root decision work item
    |
    +--> research request
            |
            +--> retrieve internal principles
            +--> retrieve authoritative guidance
            +--> inspect existing patterns
            |
            +--> synthesize returned evidence, if needed
    |
    +--> resume original decision using the evidence bundle
```

Persist `origin_work_item_id`, dependencies, child IDs, and continuation state so ownership remains clear across process restarts.

Track work depth, work-item count, model-call count, and LangGraph scheduler iterations separately. LangGraph's recursion limit alone is not a semantic no-progress detector.

### 8.3 Parallel execution

The MVP must demonstrate two independent native evidence requests running concurrently. Workers receive independent state snapshots and return results merged by stable IDs. Presentation order must be deterministic even when completion order is not.

Limit concurrency. Preserve distinctions between required and optional children. A failed optional child can yield a limited bundle; a failed required child must prevent a false success.

The initial Claude Code handoff may process host work sequentially. Do not claim several operations in one interactive host conversation are independent parallel model workers. The same contracts should permit real parallel executors later.

### 8.4 No-progress and cycle detection

Fingerprint a work attempt using the normalized request, requested output schema, scope/repository revision, evidence revision, option/criterion versions, and relevant policy version.

Repeatedly asking the same question with unchanged inputs does not count as progress. Rewording an equivalent summary must not reset the guard. Retrying is justified only by a transient execution error or materially changed evidence, requirements, options, criteria, or authorization.

Detect cycles in dependencies and repeated equivalent requests. Return a partial or blocked result with the unresolved question when further work cannot help within the budget.

### 8.5 Node versus subgraph

Use a reusable graph for genuine multi-step decision or research behavior. A single exact validator or classifier call may remain an ordinary node/function. Map parent and child state explicitly instead of leaking framework-internal objects through contracts. LangGraph supports composing subgraphs with shared or transformed state; see [G2](2026-09-30-leafcutter-kernel-spec-rev3-8-audit-links-handoff.md#g2-subgraphs-and-state-mapping).

## 9. Jev adapter and evidence-based decisions [MVP]

### 9.1 Use the existing LangChain integration

Use `langchain-typesafe` and its `TypeSafeClassifier` Runnable. The documented Python interface passes both `state` and `questions` to each invocation. `Choice` uses named criteria; `Noul` returns a yes/no probability; `Score` evaluates ordered criteria. See [J1](2026-09-30-leafcutter-kernel-spec-rev3-8-audit-links-handoff.md#j1-official-typesafe-integration-documentation) and [J5](2026-09-30-leafcutter-kernel-spec-rev3-8-audit-links-handoff.md#j5-official-package-source-and-release-metadata).

Do not implement Jev as a fake chat model, depend on text completion, or start with experimental agent middleware when a narrow classifier adapter suffices.

The verified package listing was `langchain-typesafe` **0.0.1a3**, a pre-release. Pin a compatible package version after inspecting the repository's dependency graph; record the resolved Jev model ID and adapter version. Examples copied from older integration releases may have a different call signature.

### 9.2 Illustrative adapter call

The following shows the verified API shape, not a complete routing implementation. Candidate criteria come from trusted descriptors, and the surrounding kernel still applies deterministic validation and thresholds.

```python
from langchain_typesafe import Choice, Noul, TypeSafeClassifier

classifier = TypeSafeClassifier()

route_criteria = {
    "decision": "Evaluate a bounded choice against supplied criteria and evidence.",
    "research": "Gather an evidence bundle for an unresolved information need.",
    "__NONE__": "No supplied capability can perform this known request.",
    "__NEEDS_CONTEXT__": "The request lacks enough information to choose safely.",
}

response = classifier.invoke(
    {
        "state": {
            "goal": "Determine how an existing workflow should be structured.",
            "known_context": "The caller has supplied two options and an approved ADR.",
        },
        "questions": {
            "route": Choice(
                instructions="Choose the eligible capability that advances this request.",
                criteria=route_criteria,
            ),
            "requirements_missing": Noul(
                instructions="Does the supplied task explicitly lack a necessary user requirement?"
            ),
        },
    }
)

route_answer = response.choices["route"]
selected_id = route_answer.choice
provider_confidence = route_answer.confidence
option_probabilities = route_answer.probabilities
missing_requirement_probability = response.nouls["requirements_missing"].noul
```

For asynchronous execution, use the package's asynchronous Runnable interface and propagate the invocation's callback/trace configuration. The adapter must validate provider outputs and normalize them into Leafcutter contracts.

This specification does not claim that this example was executed against live credentials. Stage 0/1 includes a real, non-sensitive integration smoke test.

### 9.3 Batching independent questions

Questions in one Jev request share the same state and are evaluated independently. Batch relevance, applicability, or evidence-category questions when each can be answered from that same state. See [J8](2026-09-30-leafcutter-kernel-spec-rev3-8-audit-links-handoff.md#j8-question-primitives-and-independence).

Do not expect question B to see question A's answer in the same request. For dependent decisions, combine results in code and make a subsequent call if needed. Batch size and payload limits must be checked against the pinned provider configuration.

Several questions in one request are not the same as several requests over different states. Additional question definitions are not free, and latency/savings claims must be measured on the actual workload. [J2](2026-09-30-leafcutter-kernel-spec-rev3-8-audit-links-handoff.md#j2-building-a-harness-with-jev) explains the batching motivation; it is not a Leafcutter performance guarantee.

### 9.4 Separate assessment from authorization and completeness

Apply exact checks first: permissions, schema compatibility, required evidence presence, approved policy constraints, and remaining budgets.

Jev then evaluates bounded semantic questions. Preserve the raw distribution and provider confidence. TypeSafe documents confidence as a statistic derived from the distribution; `Noul` does not supply that separate field. See [J6](2026-09-30-leafcutter-kernel-spec-rev3-8-audit-links-handoff.md#j6-confidence-semantics).

Do not interpret a confidence value of `0.90` as “90% probability the feature is fully specified.” Use configurable, risk-specific decision thresholds that are evaluated on representative tasks.

For a decision to be considered resolved, the runtime must independently establish:

```text
required evidence conditions are satisfied
AND required criteria have explicit assessments
AND selected option is a supplied, valid option
AND unresolved blocking contradictions are absent
AND applicable decision policy permits the selection
AND any required human approval has been obtained
```

When trade-offs themselves are unknown, request analysis or human preference. Do not force an architectural judgment into a classifier merely to keep Claude out of the process.

### 9.5 Missing knowledge and open-ended work

Start with a finite missing-knowledge taxonomy:

```text
missing_task_fact
unknown_options
missing_decision_basis
missing_authoritative_guidance
missing_internal_principle
conflicting_evidence
missing_implementation_fact
human_preference_or_authorization
```

Jev selects applicable categories. The application maps them to known request templates. A generative capability may formulate the actual question, propose new options, or synthesize a comparison, but the kernel validates every resulting request.

Keep generation limited to the requested purpose. A synthesis result may explain a disagreement without taking authority to resolve it.

### 9.6 Modalities and evidence limits

Jev's documented current input is text/structured text, not direct image input; see [J7](2026-09-30-leafcutter-kernel-spec-rev3-8-audit-links-handoff.md#j7-models-input-limits-and-versioning). A text-based diagram representation can be evidence. A claim about pixels requires a vision-capable source or verifier.

Textual consistency checking is not independent verification that an object appears in an image, a diagram accurately depicts a system, or code satisfies all behavior. Do not turn earlier vision-verification ideas into unsupported MVP guarantees.

## 10. Generic decision and research capabilities [MVP]

### 10.1 Decision flow

```text
Validated decision request
    |
    v
Load current options, criteria, constraints, and relevant evidence
    |
    v
Validate required facts and applicable decision basis
    |
    +--> missing options --> options request
    +--> missing evidence --> research/evidence request
    +--> unclear trade-offs --> analysis/synthesis request
    +--> unknown preference or approval --> human interaction
    |
    v
Evaluate atomic criteria; combine according to approved rules
    |
    v
Record recommendation, evidence links, limitations, and approval state
```

Retrieve applicable ADRs or principles when available. Validate their scope, version, assumptions, and relevance to the current framework/project version. An existing implementation is evidence of a pattern, not automatic proof that the pattern is correct or mandatory.

When enough evidence is available, a recommendation may be resolved without generating a new ADR. Formal ADR drafting/adoption is a later-stage workflow unless explicitly requested as a read-oriented output artifact.

### 10.2 Research flow

The graph is domain-agnostic:

| Evidence need | Question it answers |
|---|---|
| `authoritative_guidance` | What does the relevant official or authoritative source establish? |
| `internal_principles` | Which approved rules or constraints govern this project? |
| `prior_decisions` | Has this choice been made before, and under which assumptions? |
| `existing_patterns` | How is related behavior currently implemented? |
| `task_context` | What facts and requirements are specific to this request? |
| `external_practices` | What relevant alternatives or experience merit comparison? |

The research capability:

1. Selects evidence needs from this catalog, preserving mandatory categories established by the caller or policy.
2. Resolves eligible sources from project metadata and source registrations.
3. Creates bounded retrieval requests, parallel where independent.
4. Collects exact evidence, provenance, source availability, and limitations.
5. Requests synthesis only when raw evidence cannot support the next bounded evaluation.
6. Returns an evidence bundle or further requests with explicit continuation state.

Task-specific names such as “LangGraph” or “PostgreSQL” belong in request data and source metadata—not in the generic research topology.

### 10.3 Source resolution and retrieval

Use existing Leafcutter source access and project metadata first. For the MVP, one real local document/repository adapter plus a bounded host research path is sufficient.

The native adapter must return inspectable evidence, not just an LLM-written answer. Each result must include source identity, location, revision where available, content hash or snapshot, and any truncation.

A documentation source may be mapped to official framework documentation when the task metadata identifies that framework. An internal-principle request may map to a project's ADR directory. The evidence category is stable; the source binding varies.

Unavailable credentials, network access, or sources must remain visible. A failed fetch is not a successful search with no results.

### 10.4 Options and synthesis

The generative output contract should include relevant options, findings, constraints, agreements, disagreements, assumptions, and unresolved questions with source references.

Options are proposals. Generated criteria are proposed criteria until the applicable approval rule accepts them. A model must not resolve missing user preference by quietly changing the criteria or their weights.

The synthesis capability can perform genuine analysis when asked; the separation is about **authority and output contract**, not an artificial prohibition on reasoning.

### 10.5 Research stop conditions

Stop when the requested evidence needs are satisfied, when further permitted retrieval has no useful expected progress, or when a guard is reached.

Do not research indefinitely merely to increase a confidence score. Preserve conflicting sources instead of averaging them into artificial certainty. Return unknowns, unavailable sources, and unresolved trade-offs explicitly.
