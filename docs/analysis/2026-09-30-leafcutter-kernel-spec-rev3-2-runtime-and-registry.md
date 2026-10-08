---
title: "Leafcutter Kernel Specification Rev 3 - Part 2 of 8"
description: "In-tree copy of the Revision 3 Leafcutter decision-kernel specification (30 September 2026), part 2 of 8: runtime architecture and registry routing eligibility (sections 5-6). Text is verbatim; only cross-part anchor links were rewritten."
type: reference
status: active
created: 2026-09-30
last_updated: 2026-09-30
components:
  - decision_kernel
---

> Source-of-truth specification for TICKET-20260930-KernelBootstrapV0, copied from the workspace file `leafcutter_kernel_bootstrap_specification.md`. Part 2 of 8 ([previous part](2026-09-30-leafcutter-kernel-spec-rev3.md) | [next part](2026-09-30-leafcutter-kernel-spec-rev3-3-contracts.md)). Split only to satisfy the 300-line doc limit.

# Part B — MVP implementation specification

## 5. Runtime architecture and invocation boundary [MVP]

```text
Claude Code skill / future client
    |
    | start / resume / status / cancel
    v
Leafcutter application service + CLI serialization adapter
    |
    v
LangGraph kernel scheduler
    |
    +--> normalize task and apply fixed rules
    +--> select ready work from the agenda
    +--> load pinned, eligible capability descriptors
    +--> Jev routing assessment
    +--> deterministic dispatch
    |       |
    |       +--> native graph or function
    |       +--> read-only source adapter
    |       +--> persisted host-work handoff
    |       +--> persisted human question
    |
    +--> validate result and merge evidence
    +--> register child requests or resume parent continuation
    +--> enforce limits and root completion requirements
    |
    v
Run envelope + decision report + evidence references + trace references
```

A capability receives only its validated request, relevant evidence references or selected excerpts, constraints, and execution context. It does not receive the entire repository or all run history by default.

The kernel may choose between native and approved host-backed implementations, but a capability cannot bypass the kernel to call arbitrary peers. Capabilities return requests for additional work; the kernel schedules them.

### 5.1 Application API

Implement these operations in the application layer, then expose them through CLI serialization:

```text
start_run(TaskInput) -> RunEnvelope
resume_run(run_id, InteractionSubmission) -> RunEnvelope
get_run(run_id) -> RunEnvelope
cancel_run(run_id, actor) -> RunEnvelope
```

Capability execution has one normalized boundary:

```text
CapabilityExecutor.ainvoke(CapabilityInvocation, ExecutionContext)
    -> CapabilityResult
```

`ExecutionContext` contains runtime dependencies such as authorized source clients, model clients, tracing handles, timeouts, and cancellation. These dependencies are not serialized into graph state.

### 5.2 Capability catalog versus source catalog

Keep these concepts separate:

- A **capability catalog** says what kinds of work the runtime can perform.
- A **source catalog** says where evidence may be obtained and what access/version constraints apply.

A request for `authoritative_guidance` must not hard-code “search the LangGraph website.” Source resolution derives relevant technologies or domains from the task/project metadata and selects suitable registered sources.

Reuse existing Leafcutter representations. The MVP does not require a new database merely to model these concepts.

## 6. Capability registry adaptation and routing eligibility [MVP]

Normalize each existing registry record into a `CapabilityDescriptor`. Preserve the registry's source identity and version.

Before invoking Jev, deterministic code must filter candidates by:

- Enabled status and implementation availability.
- Supported input and output schemas.
- Request type and supported operation.
- Repository, component, and execution scope.
- Credentials and source access.
- Side-effect class and caller authorization.
- Configured budget and concurrency constraints.

**Semantic fit is not authorization.** A model-selected capability must still pass every deterministic check before dispatch.

Use a stable registry snapshot for an active run. Do not resume an old continuation against a silently changed implementation. If the pinned version is unavailable, return an explicit compatibility blocker or apply an approved migration.

### 6.1 Routing outcomes

| Outcome | Meaning | Kernel behavior |
|---|---|---|
| `selected` | An eligible capability can advance the request | Validate the ID and invoke it |
| `insufficient_context` | The goal, inputs, or candidate distinction is unclear | Request clarification/evidence or an explicitly allowed analysis operation |
| `no_match` | No catalog capability fits the known need | Record a capability gap; consider an approved host fallback |
| `unavailable` | A suitable capability exists but cannot currently run | Report availability, compatibility, or permission problem; do not relabel it as a missing capability |

A low score alone does not prove a capability is missing. Distinguish ambiguous input, an incomplete catalog search, an unavailable implementation, and a genuinely unsupported kind of work.

Kernel housekeeping—recording gaps, validation, persisting interactions, and finalization—is fixed control flow. Do not recursively ask Jev which graph should perform every bookkeeping operation.
