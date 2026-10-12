---
title: "Leafcutter Kernel Specification Rev 3 - Part 3 of 8"
description: "In-tree copy of the Revision 3 Leafcutter decision-kernel specification (30 September 2026), part 3 of 8: canonical input/output contracts (section 7). Text is verbatim; only cross-part anchor links were rewritten."
type: reference
status: active
created: 2026-09-30
last_updated: 2026-09-30
components:
  - decision_kernel
---

> Source-of-truth specification for TICKET-20260930-KernelBootstrapV0, copied from the workspace file `leafcutter_kernel_bootstrap_specification.md`. Part 3 of 8 ([previous part](2026-09-30-leafcutter-kernel-spec-rev3-2-runtime-and-registry.md) | [next part](2026-09-30-leafcutter-kernel-spec-rev3-4-scheduler-jev-capabilities.md)). Split only to satisfy the 300-line doc limit.

## 7. Canonical input/output contracts [MVP]

### 7.1 Representation rules

Use Leafcutter's existing typed-model convention, preferably Pydantic if already used. Export JSON Schema and keep valid/invalid JSON fixtures for all external boundaries.

Every persisted entity has a stable ID, `schema_version`, and UTC timestamps. IDs are strings. Optional values use explicit `null` where relevant. Collections use independent defaults; do not create shared mutable defaults. Do not serialize executable objects, callbacks, arbitrary Python instances, or graph runtimes.

Named payloads must have registered schemas. A `dict[str, Any]` escape hatch must not replace validation of the core protocol. Unknown fields at external submission boundaries should be rejected unless an explicitly versioned extension field permits them.

The following are canonical contracts, not a requirement to create one database table or package per contract.

### 7.2 Task, scope, and constraints

| Contract | Required fields and meaning |
|---|---|
| `TaskInput` | `goal`, caller identity, `scope`, optional initial evidence, optional constraints, requested output schema, caller permissions |
| `Task` | `id`, `root_task_id`, optional `parent_task_id`, original goal, optional classified intent, scope, initial evidence references, constraint references, requested output schema, root-work-item reference |
| `Scope` | Repository/workspace ID, revision or working-tree snapshot identity, optional component IDs, authorized read roots, source/data-access context |
| `Constraint` | Stable ID, kind, structured value or text, source reference, severity, origin, and authority/approval state when applicable |

The kernel—not a model—assigns IDs, root identity, execution permissions, and authoritative persistence metadata.

Preserve the original user request separately from normalized or model-interpreted versions. Intent classification must not silently rewrite the goal.

### 7.3 Evidence and findings

| Contract | Required fields and meaning |
|---|---|
| `EvidenceSource` | Source ID, kind, locator, title, source version where known, retrieved time, observed publication/modification metadata, exact section/line locator where available |
| `Evidence` | ID, semantic evidence type, raw excerpt or artifact reference, source reference, content hash, provenance, access classification, verification status, known limitations |
| `Finding` | Claim text, supporting evidence IDs, contradicting evidence IDs, limitations, producer/version, and whether it is a source fact, inference, assumption, or reported human input |
| `EvidenceNeed` | ID, semantic category, question or fact needed, required/optional status, relevant scope, acceptable source conditions, retrieval resolution, and completion status |
| `EvidenceBundle` | Question/request ID, evidence/finding references, coverage by evidence need, attempted sources, unavailable sources, limitations, contradictions, and truncation indicators |

Initial evidence categories:

```text
authoritative_guidance
internal_principles
prior_decisions
existing_patterns
task_context
external_practices
```

Repository facts, documentation facts, human input, and synthesized findings remain distinguishable by source/finding metadata. Avoid inventing a separate evidence category for every framework or vendor.

Do not confuse retrieval time with source freshness. A page retrieved today may describe an old release. Repository evidence must retain its revision or working-tree snapshot identity.

A model-generated summary is not independently verified evidence. It must retain links to the underlying material and label inferences. Missing evidence is not evidence that a feature, policy, or risk is absent.

### 7.4 Requests and execution records

| Contract | Required fields and meaning |
|---|---|
| `Request` | ID, origin work-item ID, kind, goal/question, validated payload and payload schema, requested output schema, evidence needs, blocking/supporting priority, scope, context references, dependencies, deduplication key |
| `WorkItem` | ID, root task ID, request ID, status, dependency IDs, child IDs, continuation state, bound capability ID/version when selected, attempt count, depth, result reference |
| `CapabilityInvocation` | Invocation ID, work-item ID, capability ID/version, validated input, selected context/evidence references, continuation payload, input fingerprint, attempt number, trace context |

Initial request kinds are:

```text
evidence
options
synthesis
human
capability
```

The payload schema and requested output schema distinguish, for example, an evidence-planning request from an exact retrieval request. Add new request kinds only when their lifecycle differs meaningfully—not simply because a new capability was added.

A `Request` describes missing work. A `WorkItem` tracks its execution. The graph's continuation state belongs to the **owning capability work item**, not to a Python call stack.

### 7.5 Capability descriptors

`CapabilityDescriptor` must include:

```text
id, version, description
supported request kinds and operations
accepted payload schema IDs
produced output schema IDs
scope/component tags
implementation binding and execution mode
side-effect class
permission requirements
availability and configuration status
cost/latency hints if known
registry origin and version
```

Implementation bindings resolve only through trusted application registration. Never import a module, run a shell command, or evaluate Python because Jev or a retrieved document returned its name.

Execution mode may be `native` or `host_handoff`. A host-backed capability is not a native graph merely because it has a registry entry.

### 7.6 Capability results and status normalization

Use one executor result protocol:

```text
CapabilityResult
  invocation_id
  work_item_id
  status: completed | waiting | partial | blocked | failed
  output_schema_id
  output_payload
  evidence[]
  findings[]
  decisions[]
  requests[]
  continuation_state
  usage
  error / diagnostics
```

Lifecycle invariants:

- **`completed`** resolves that work item only. It cannot include actionable unfinished child requests.
- **`waiting`** requires at least one actionable child request or a persisted host/human interaction. It must carry enough continuation state to resume the owning capability.
- **`partial`** returns useful incomplete work with explicit limitations and no expectation of automatic continuation. An unfinished dependency is `waiting`, not `partial`.
- **`blocked`** identifies an unmet prerequisite that cannot currently be resolved within permissions, available capabilities, or remaining budgets.
- **`failed`** describes an execution or validation failure, not ordinary uncertainty.

Earlier discussion names map to this normalized protocol:

| Earlier name | Canonical representation |
|---|---|
| `RESOLVED` capability result | `completed` |
| `NEEDS_INFORMATION` | `waiting` plus evidence requests |
| `NEEDS_REASONING` / `NEEDS_SYNTHESIS` | `waiting` plus an appropriate generative request |
| `NEEDS_OPTIONS` | `waiting` plus an options request |
| `NEEDS_HUMAN` | `waiting` plus a persisted human interaction |
| `NO_CAPABILITY` | Routing outcome `no_match`, a gap record, and either approved fallback or a blocked result |

This normalization avoids maintaining multiple overlapping result enums whose transitions contradict one another.

### 7.7 Options, criteria, decisions, and routing assessments

| Contract | Required fields and meaning |
|---|---|
| `Option` | Stable ID, title, description, assumptions/constraints, source/finding references, and proposal status |
| `Criterion` | Stable ID, question, required/supporting designation, applicable scope, decision basis, approved weight/rule where relevant |
| `CriterionAssessment` | Criterion ID, option ID where relevant, outcome, evidence references, provider response or deterministic result, limitations |
| `Decision` | ID, question, options, criterion references, selected option ID, assessment status, approval status, evidence references, missing needs, recorded rationale, versions, and unresolved risks |
| `RoutingAssessment` | Eligible candidate IDs, selected candidate or sentinel, raw response/distributions, provider confidence, template/model version, evidence revision, outcome, and reason-category codes |

Decision assessment statuses:

```text
resolved
needs_evidence
needs_options
needs_synthesis
needs_human
blocked
```

Decision approval statuses:

```text
not_required
proposed
approved
rejected
```

An assessed recommendation is not automatically an approved architectural decision. Record who or which authorized policy permits adoption.

Keep `provider_confidence`, per-option probabilities, evidence coverage, and approval status separate. Do not compress them into one “90% ready” field.

A rationale is a concise evidence-and-criteria explanation assembled by a template or generative capability. Label its origin. Do not claim it is a transcript of Jev's hidden reasoning.

### 7.8 Host and human interactions

| Contract | Required fields and meaning |
|---|---|
| `HostWorkRequest` | Interaction ID, work-item/invocation IDs, operation, exact goal, selected input/evidence references, approved tools/sources, forbidden actions, output schema, context limits, trace context |
| `HumanQuestion` | Interaction ID, unresolved decision, question, relevant evidence, optional choices with consequences, free-text policy, why research cannot settle it, required actor/approval role |
| `InteractionSubmission` | Run ID, interaction ID, expected state revision, actor identity, validated response/result, optional new evidence, usage metadata with origin |

Validate that a submission refers to the currently pending interaction and expected work item. A generative response cannot impersonate a human answer, grant itself permissions, or directly approve a policy.

An identical duplicate submission is idempotent. A conflicting duplicate or stale submission is rejected without losing run state.

### 7.9 Usage, capability gaps, and run output

`Usage` records provider-reported tokens, duration, observed cost where available, estimates where explicitly identified, and provenance. Unknown values remain `null`/unavailable—not zero.

`CapabilityGap` records the known goal, normalized unmet need, requested input/output shape, scope, registry snapshot, candidates considered, why they were insufficient, gap type, occurrence count, fallback outcome, and proposed capability metadata if available. A proposal is not a live registry entry.

`RunEnvelope` contains:

```text
run_id, root_task_id, state_revision
status: running | waiting_host | waiting_human |
        completed | partial | blocked | failed | cancelled
requested-output payload or report reference
decision and evidence references
open questions and pending interactions
limitations and capability gaps
usage summary
trace references
```

### 7.10 Kernel state and invariants

Persist:

```text
root task and pinned registry snapshot
work-item map, ready agenda, dependency relationships
pending host/human interactions
request, evidence, finding, decision, and result indexes
per-work-item continuation state
event sequence and state revision
budgets, usage, no-progress fingerprints
run status and final-result reference
```

Large content belongs in an artifact/evidence store; graph state should primarily hold references and compact working data. Reuse existing storage facilities.

**Only the kernel changes lifecycle state.** A capability result proposes output and follow-up work; it does not mutate global state directly. A child completing does not complete the root task.


### 7.11 Initial payload and output schema catalog

Register these schemas, or explicit compatible mappings onto existing Leafcutter schemas. The names below are proposed stable protocol IDs; they are not arbitrary model-generated schema names.

| Schema ID | Required payload |
|---|---|
| `leafcutter.decision_request.v1` | Question, supplied option IDs/descriptions, criterion IDs/definitions or an explicit indication that criteria are missing, evidence references, constraints, approval requirements, and requested decision scope |
| `leafcutter.decision_report.v1` | Recommendation or unresolved status, selected option if any, criterion assessments, supporting/contradicting evidence, open questions, approval state, limitations, and trace references |
| `leafcutter.research_request.v1` | Research question, evidence needs, source restrictions, scope, existing evidence, and expected coverage |
| `leafcutter.retrieval_request.v1` | Information need, evidence category, eligible source references, scope, desired detail/resolution, and result limits |
| `leafcutter.evidence_bundle.v1` | Evidence/finding references, coverage against requested needs, attempted/unavailable sources, contradictions, and limitations |
| `leafcutter.options_request.v1` | Problem, known constraints, existing alternatives, relevant evidence, requested option count limit, and proposal requirements |
| `leafcutter.options.v1` | Options with stable IDs, descriptions, assumptions, source references where available, and explicitly unresolved feasibility claims |
| `leafcutter.synthesis_request.v1` | Exact question/operation, selected evidence references, output requirements, and analysis limits |
| `leafcutter.findings.v1` | Source-linked findings, agreements/disagreements, constraints, assumptions, and remaining unknowns |

Schema validation verifies structure, types, and references—not the truth of a claim. Add semantic checks where required, such as verifying that cited evidence actually exists and that a selected option was supplied.

For generated JSON Schema supplied through `required_output_schema`, accept only a supported declarative subset with bounded complexity. Disable remote schema resolution and executable extensions. Prefer registered schema IDs for the initial MVP.

The root request must choose a supported output contract. A completed evidence bundle resolves a research request; it does not by itself satisfy a root request for a decision report.
