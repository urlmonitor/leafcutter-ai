---
title: "ADR-055: The Kernel's Capability Registry Starts Empty — Legacy Agents and Skills Enter Only by Recorded Decision"
description: "The Decision Kernel routes only over a new config/capability_registry.json that starts empty, never over the legacy agent, skill, workflow or command registries. A legacy asset becomes routable only through a legacy_admission entry whose decision_ref names an ADR, so nothing reaches Jev's routing without a recorded decision that it meets the capability contract."
type: "adr"
status: "active"
created: "2026-09-30"
last_updated: "2026-09-30"
deciders:
  - BrainCandy
components:
  - decision_kernel
related_docs:
  - docs/architecture/adrs/ADR-052-capabilities-replace-agents-prompts-are-compiled.md
  - docs/architecture/adrs/ADR-054-process-representation-and-maturity-model.md
  - docs/architecture/components/decision-kernel.md
  - docs/analysis/2026-09-30-decision-kernel-design.md
  - docs/analysis/2026-09-30-decision-kernel-design-2-contracts-registry-config.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-2-runtime-and-registry.md
  - tickets/00_inbox/TICKET-20260930-KernelBootstrapV0.md
related_code:
  - config/capability_registry.json
  - config/capability_registry.schema.json
  - kernel/contracts/capability.py
  - kernel/registry/
---

# ADR-055: The Kernel's Capability Registry Starts Empty — Legacy Agents and Skills Enter Only by Recorded Decision

## Status

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-09-30 |
| Deciders | BrainCandy |
| Author | Claude Code, recording BrainCandy's binding decision 3 of [TICKET-20260930-KernelBootstrapV0](../../../tickets/00_inbox/TICKET-20260930-KernelBootstrapV0.md) |
| Supersedes | None. Deliberately deviates from kernel spec Rev 3 §2.1(3) and §6. |

## Context

The kernel specification, Revision 3, settles that the kernel reuses Leafcutter's existing
capability registry: "Normalize its descriptors through an adapter rather than creating a
competing registry" ([spec part 1](../../analysis/2026-09-30-leafcutter-kernel-spec-rev3.md),
§2.1(3)); "Normalize each existing registry record into a `CapabilityDescriptor`"
([spec part 2](../../analysis/2026-09-30-leafcutter-kernel-spec-rev3-2-runtime-and-registry.md), §6).

The registries that exist today (`config/agent_registry.json`, `config/skill_registry.json`, and
the workflow and command surfaces) describe agent personas and prompt-driven skills. They carry
no input or output contract. [ADR-052](ADR-052-capabilities-replace-agents-prompts-are-compiled.md)
makes the contract-driven capability, not the agent, the kernel's unit of work. Normalizing
those records would make every legacy entry offerable to Jev's routing without anyone having
decided that it meets that contract.

On 2026-09-30 BrainCandy overrode the spec on this point (ticket binding decision 3). The kernel
design records the override as deliberate deviation 1
([design part 1](../../analysis/2026-09-30-decision-kernel-design.md)) and specifies the new
registry and its admission rule
([design part 2](../../analysis/2026-09-30-decision-kernel-design-2-contracts-registry-config.md)).
ADR-052 and [ADR-054](ADR-054-process-representation-and-maturity-model.md) (§8) both rely on
this rule. This ADR records it.

## Decision

### 1. The kernel reads one registry, and it starts empty

The kernel MUST read routable capabilities only from `config/capability_registry.json`,
validated against `config/capability_registry.schema.json`. The file MUST start with an empty
`capabilities` list. Capabilities are added entry by entry, each with an `admission` record.

### 2. Legacy registries are never read

The kernel MUST NOT read, normalize or route over the legacy agent, skill, workflow or command
registries. There MUST be no bulk import path from them into `config/capability_registry.json`.

### 3. A legacy asset enters only by an explicit, recorded decision

A capability derived from a legacy agent or skill MUST carry an `admission` of kind
`legacy_admission`, with `legacy_source: {registry, id}` and a `decision_ref` that names an
ADR (`^ADR-\d{3}$`). A ticket reference MUST NOT satisfy a legacy admission. Each admission is
its own decision. This ADR admits no legacy asset.

### 4. The spec's registry rules still apply, over the new registry

Spec §6's deterministic eligibility filter, snapshot pinning and descriptor normalization MUST
still apply. They run over `config/capability_registry.json` instead of the legacy registries.
Native kernel capabilities enter through `native_registration`, as design part 2 specifies.

## Consequences

### Positive

- Jev routes only over capabilities that someone deliberately registered, each with declared
  schemas, permissions and side effects.
- Every legacy-derived entry traces to the ADR that admitted it.
- A persona prompt cannot become routable by accident, which keeps ADR-052's capability model
  intact.

### Negative

- The kernel has no routable capability until native entries are registered (phase P5 in
  [design part 6](../../analysis/2026-09-30-decision-kernel-design-6-tests-phases-risks.md)).
- Useful legacy agents and skills stay out of reach of the kernel until each one is admitted by
  its own ADR.
- Two registry families coexist, and spec §2.1(3) and §6 no longer describe this repository on
  this point.

### Operational

- `config/capability_registry.json` states the rule in its `_comment`.
- The registry loader rejects an entry without `admission`, and a `legacy_admission` without
  `legacy_source` or without an ADR `decision_ref` (`kernel/contracts/capability.py`,
  `kernel/registry/`).
- Admitting a legacy asset means writing its ADR first and then adding the entry with that
  ADR as `decision_ref`.

## Alternatives

- **Reuse the existing registries, as the spec says.** Rejected. Legacy records describe
  personas and prompts, not input and output contracts. Normalizing them would make each one
  routable without a decision that it fits the capability contract of ADR-052.
- **Import all legacy entries once into the new registry.** Rejected. A one-time bulk import has
  the same effect as reuse, frozen at import time. Every entry becomes routable, and none traces
  to a decision about that entry.

## References

- Originating decision: binding decision 3 in
  [TICKET-20260930-KernelBootstrapV0](../../../tickets/00_inbox/TICKET-20260930-KernelBootstrapV0.md),
  made by BrainCandy on 2026-09-30.
- [ADR-052: Capabilities replace agents; prompts are compiled](ADR-052-capabilities-replace-agents-prompts-are-compiled.md)
- [ADR-054: Process representation and maturity model](ADR-054-process-representation-and-maturity-model.md), §8
- [Decision Kernel component](../components/decision-kernel.md)
- Kernel design [part 1](../../analysis/2026-09-30-decision-kernel-design.md) (deviation 1) and
  [part 2](../../analysis/2026-09-30-decision-kernel-design-2-contracts-registry-config.md)
  (registry and admission)
