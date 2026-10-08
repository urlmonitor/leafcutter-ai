---
title: "Leafcutter Kernel Specification Rev 3 - Part 6 of 8"
description: "In-tree copy of the Revision 3 Leafcutter decision-kernel specification (30 September 2026), part 6 of 8: capability gaps, build sequence and MVP exit gate (sections 14-16). Text is verbatim; only cross-part anchor links were rewritten."
type: reference
status: active
created: 2026-09-30
last_updated: 2026-09-30
components:
  - decision_kernel
---

> Source-of-truth specification for TICKET-20260930-KernelBootstrapV0, copied from the workspace file `leafcutter_kernel_bootstrap_specification.md`. Part 6 of 8 ([previous part](2026-09-30-leafcutter-kernel-spec-rev3-5-client-observability-safeguards.md) | [next part](2026-09-30-leafcutter-kernel-spec-rev3-7-later-stages.md)). Split only to satisfy the 300-line doc limit.

## 14. Capability gaps and bootstrap learning [MVP]

“No suitable capability” is useful product feedback, not permission to invent and execute a new graph.

A gap record must retain the exact unmet need, requested output, relevant scope, registry snapshot, candidate assessment, missing native implementation if applicable, and fallback result.

Differentiate:

- A genuinely unsupported capability.
- A known capability with only a host-backed implementation.
- A temporary provider/configuration failure.
- A permission restriction.
- Ambiguous input that cannot yet be routed.

Only the first two describe implementation opportunities. The others must not create misleading “build a new graph” tickets.

Deduplicate gaps by normalized need, input/output contract, and relevant scope. Preserve occurrence counts and example run IDs. A single vague request is not sufficient evidence that an entirely new subsystem is needed.

A local backlog-ready artifact can be generated from these records. It should include proposed purpose, input/output contracts, examples, expected benefit, closest existing capabilities, and remaining uncertainties. Its author must be identified as a template or generative proposer; Jev does not generate arbitrary ticket prose.

Approved host fallback may complete bounded synthesis, options, question formulation, or research. A denied native action must not be reclassified as a missing capability and routed through a permissive fallback.

Use observed fallback frequency, total cost where known, latency, failure rate, and usefulness to prioritize new native capabilities. New code is implemented, tested, reviewed, versioned, and registered through the normal development process—not installed automatically by the kernel.

## 15. Build sequence and implementation deliverables [STAGES 0–1]

### 15.1 Stage 0: inspect before adding abstractions

Locate existing:

```text
capability registry and descriptor formats
glossary and component-directory access
configuration and secret handling
model-client conventions
source/repository access helpers
logging and observability facilities
persistence/checkpoint infrastructure
CLI entry points and test conventions
```

Produce a short mapping from existing modules to the interfaces in this specification. Identify compatibility problems and remaining unknowns without inventing repository paths.

Verify Jev with non-sensitive synthetic input and Langfuse with a demonstration observation. Pin compatible dependency versions rather than upgrading the repository indiscriminately.

Record the provisional bootstrap choice: **tested Python/LangGraph implementations for the first kernel and native capabilities**. This is necessary to make the research mechanism exist. The runtime does not need to solve its own entire architecture before it can run.

### 15.2 Stage 1 implementation order

1. Canonical contracts, schema fixtures, service facade, and registry adapter.
2. Durable work/run state and local event records, with Langfuse integration immediately.
3. Jev adapter, routing eligibility, and deterministic provider test doubles.
4. Kernel scheduling, isolated invocation, result validation, parent continuation, and root completion.
5. Native decision graph, small generic research graph, and one real read-only source adapter.
6. Persistent human/host interactions and validated resume semantics.
7. CLI transport and minimal `/leafcutter` skill.
8. Bounded synthesis/options/question/research host operations, including actual resumed execution.
9. Capability gaps, fallback accounting, cancellation, deduplication, no-progress controls, and parallel native requests.
10. Full offline tests, a separate live integration suite, and the demonstration report/trace.

### 15.3 Suggested package boundaries

Adapt to the existing repository rather than creating these exact directories blindly:

```text
contracts/
kernel/          # state, scheduling, dispatch, guards, completion
registry/        # normalization over existing registry
providers/       # Jev adapter; future model executors
capabilities/    # decision, research, source adapters, bounded host operations
adapters/        # CLI and Claude Code transport
observability/   # Langfuse integration and correlation
storage/         # reuse existing state/artifact persistence where possible
tests/           # contracts, unit, integration, live-smoke separation
```

A capability should be independently testable and replaceable without changing the kernel. Avoid a second configuration system, logging framework, or general-purpose workflow DSL.

### 15.4 Required artifacts at delivery

- Implementation and exported input/output schemas.
- Valid and invalid protocol fixtures.
- Offline tests and a clearly separated live-smoke test procedure.
- Example configuration and credential setup instructions without secrets.
- `/leafcutter` project skill and documented CLI commands.
- A sample resumed decision/research run and its structured report.
- Evidence/source snapshots or references sufficient to inspect that example.
- A working Langfuse trace reference and documented MCP read-only inspection.
- A capability-gap example and a list of explicitly deferred work.

### 15.5 First dogfooding research task

After the minimum loop works, use it to investigate:

> How should later Leafcutter capability/workflow definitions be represented: Python/LangGraph implementations, declarative JSON/YAML, or a hybrid?

Evaluate authoring, testability, state mapping, dynamic composition, permissions, versioning, review, debugging, and migration. The existing registry and fixed choice of LangGraph remain inputs, not decisions to reopen.

A hybrid is a candidate: declarative routing/policy metadata plus trusted Python implementations. It is not a preselected final answer. Produce a supported recommendation or proposed ADR; do not auto-approve or execute generated workflow definitions.

## 16. MVP verification and completion [STAGE 1 EXIT GATE]

These are engineering verification checks for the first deliverable, not a requirement to implement the later acceptance-criteria product workflow.

| Scenario | Observable required result |
|---|---|
| Existing applicable decision basis | Resolve a supported recommendation without unnecessary generative research |
| Missing decision basis | Create evidence requests, collect results, and resume the owning decision |
| Unknown options | Obtain schema-valid proposals, then evaluate supplied options rather than inventing a choice inside Jev |
| Missing human preference | Persist a question, exit cleanly, accept the answer, preserve actor identity, and resume |
| Two independent evidence needs | Execute native requests concurrently and merge deterministically |
| Child finishes before root | Root remains incomplete until its own output and required dependencies are satisfied |
| True capability gap | Persist a deduplicated gap; use approved fallback or return a blocker |
| Known but unavailable capability | Preserve availability/permission reason; do not invent a missing-capability ticket |
| Invalid host result or forged IDs | Reject submission while preserving state and pending interaction |
| Duplicate resume | Accept identical replay idempotently; reject conflicting or stale submissions |
| Process restart at handoff | Existing evidence, capability binding, and completed work survive |
| Repeated question with no new information | No-progress guard stops repetition and reports unresolved work |
| Provider failure | Preserve explicit failure diagnostics; no fabricated decision |
| Conflicting evidence | Retain the conflict and escalate when blocking; do not turn it into unsupported certainty |
| Unknown billing | Mark usage/cost unavailable rather than reporting zero |
| Malicious source instructions | Treat them as untrusted content; do not expand scope or permissions |
| Cancelled run | Reject subsequent resumes and preserve cancellation provenance |
| Trace inspection | Run, routing, evidence, host handoffs, decisions, and final state are inspectable in Langfuse |
| Different decision domain | Reuse the same generic graph without adding framework-specific source logic |

Use deterministic fake provider outputs for branch tests. Separate live Jev behavior tests from deterministic orchestration tests. A small labeled evaluation set should include unanswerable questions, missing information, contradictory evidence, and out-of-scope tasks. Report results rather than asserting calibration transfers automatically to Leafcutter.

**MVP is done when `/leafcutter` can complete a real decision/research slice through the real kernel and registry; genuinely retrieve evidence; use live Jev for the intended bounded decisions; persist and resume validated continuations; survive the documented failure paths; and produce an inspectable Langfuse trace and evidence-backed result.**

An all-mock demo, a set of graph files without continuation, or a Claude prompt that informally imitates the workflow is not the MVP.
