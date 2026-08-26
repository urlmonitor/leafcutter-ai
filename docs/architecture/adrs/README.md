---
title: Architecture Decision Records
description: Index of all Architecture Decision Records (ADRs) for the leafcutter-ai
  package, listing each decision's number, status, title, and date.
type: reference
created: '2026-08-13'
last_updated: '2026-08-26'
status: active
components:
- documentation_system
---

# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for the leafcutter-ai
package. ADRs document significant architectural decisions — the context, the choice
made, and the consequences — so that future contributors can understand *why* things
are the way they are.

Every ADR owns exactly one integer. Regenerate this index after adding or
renumbering an ADR:

```bash
python scripts/adr_refs.py --index --write
```

## Index

| # | Status | Title | Date |
|---|--------|-------|------|
| [ADR-001](ADR-001-self-hosting-boundary.md) | Active | Self-Hosting Boundary — Config-Driven Path Resolution | 2026-08-13 |
| [ADR-002](ADR-002-dual-platform-compilation.md) | Active | Dual Platform Compilation for AI Agents | 2026-05-22 |
| [ADR-003](ADR-003-test-source-of-truth-discipline.md) | Accepted | Tests Are Mirrors of Production Contracts — Contract Shrinkage During Test Repair Requires Explicit Authorization | 2026-05-22 |
| [ADR-004](ADR-004-consolidated-output-root.md) | Active | Consolidated Output Root — All build.py Artifacts Under .leafcutter/ | 2026-05-27 |
| [ADR-005](ADR-005-frontend-coder-agent.md) | Active | frontend-coder as a First-Class Sibling Implementation Agent | 2026-05-28 |
| [ADR-006](ADR-006-flatten-supervisor-chain.md) | Accepted | Flatten the Supervisor Chain — ticket-supervisor at Depth 0 | 2026-05-29 |
| [ADR-007](ADR-007-contract-driven-acs.md) | Accepted | Contract-Driven Acceptance Criteria | 2026-06-04 |
| [ADR-008](ADR-008-ac-store-schema-id-format-enforcement.md) | Accepted | AC Store — YAML Schema, ID Format, and Bidirectional Enforcement Model | 2026-06-04 |
| [ADR-009](ADR-009-itpo-no-source-code-access.md) | Accepted | IT Product Owner v3 — Source Code Access Restriction | 2026-06-05 |
| [ADR-010](ADR-010-ac-store-as-authoritative-backlog.md) | Accepted | AC Store as Authoritative Backlog — Source-of-Truth Inversion | 2026-06-05 |
| [ADR-011](ADR-011-learning-emission-sink.md) | Active | Learning Emission Sink — Separate knowledge_emissions.jsonl vs Reuse | 2026-06-05 |
| [ADR-012](ADR-012-retire-create-ticket-js.md) | Accepted | Retire create-ticket.js — /plan-feature + /build-ac as Canonical Ticket-Creation Path | 2026-06-16 |
| [ADR-013](ADR-013-portable-skill-script-deployment-boundary.md) | Accepted | Portable Skill Script Deployment Boundary — Consumer-Facing vs Package-Internal | 2026-06-17 |
| [ADR-014](ADR-014-exception-guard-enforcement-scope.md) | Accepted | Exception-Handling Guard Enforcement Scope | 2026-06-17 |
| [ADR-015](ADR-015-guard-honors-noqa-ble001.md) | Active | Exception-Handling Guard Honors Inline `# noqa: BLE001` Suppression | 2026-06-18 |
| [ADR-016](ADR-016-ci-fresh-clone-test-dependencies.md) | Active | CI Fresh-Clone Test Dependencies — Build Step Required Before Test Suite | 2026-06-24 |
| [ADR-017](ADR-017-computed-quality-gates.md) | Active | Computed Quality Gates | 2026-07-01 |
| [ADR-018](ADR-018-agent-isolation-topology.md) | Active | Agent Isolation Topology — Per-Feature Clones + Hub Branch-Protection, Retire Shared-Worktree Drives | 2026-07-06 |
| [ADR-019](ADR-019-build-feature-inline-phase-dispatch.md) | Accepted | build-feature.js Inlines the Phase-Dispatch Loop | 2026-07-09 |
| [ADR-020](ADR-020-live-surface-tester.md) | Accepted | Live Surface Tester — Port Registry, Read-Only Constraint, and Conditional | 2026-06-03 |
| [ADR-021](ADR-021-plan-feature-product-truth-phase.md) | Accepted | Always-On Product-Truth Authoring Phase in /plan-feature | 2026-07-14 |
| [ADR-022](ADR-022-mockups-are-the-real-app-in-mock-mode.md) | Proposed | Mockups Are the Real Application in Mock Mode (Data-Layer Mock Provider or Throwaway Real-DB Seed) | 2026-07-15 |
| [ADR-023](ADR-023-product-truth-flow-first-upstream-layer.md) | Accepted | Product-Truth Store as the Flow-First Upstream Layer Beside the AC Store | 2026-07-14 |
| [ADR-024](ADR-024-interactive-pause-resume.md) | Active | Interactive Gates Pause and Persist Instead of Cancelling When Headless | 2026-07-20 |
| [ADR-025](ADR-025-first-class-flow-decisions.md) | Active | Decisions Are First-Class Flow Entities, Rendered as Chained Diamonds | 2026-08-10 |
| [ADR-026](ADR-026-ac-driven-build-v2-phased-migration.md) | Active | AC-Driven Build v2 — Phased, Dogfooded, Backward-Compatible Migration | 2026-08-12 |
| [ADR-027](ADR-027-tdd-workflow-enforcement.md) | Active | Test-First Workflow Enforcement in the Agentic Build Pipeline | 2026-05-27 |
| [ADR-028](ADR-028-test-fixture-convention.md) | Proposed | Test Fixture Convention: load_fixture() Helper and tests/fixtures/ Directory Layout | 2026-06-04 |
| [ADR-029](ADR-029-adr-number-collision-prevention.md) | Active | ADR Number Collision Prevention — Pre-Commit Guard Over the Integer Sequence | 2026-08-13 |
| [ADR-030](ADR-030-dual-engine-workflow-support.md) | Active | Dual-Engine Workflow Support — Canonical E2 Authoring + Build-Time E1 Shim | 2026-07-01 |
| [ADR-031](ADR-031-worktree-quality-gate-guard.md) | Active | Worktree Quality Gate Guard — Execution-Proof Fail-Closed Design | 2026-07-06 |
| [ADR-032](ADR-032-tiered-parallel-code-smell-review.md) | Active | Tiered Parallel Code-Smell Review (Modern-12 Bucket Split + Depth-1 Orchestration) | 2026-08-11 |
| [ADR-033](ADR-033-agent-model-tiers.md) | Active | Agent Model Tiers and Gatekeeper Escalation | 2026-08-13 |
| [ADR-034](ADR-034-knowledge-write-ownership.md) | Active | Knowledge Write Ownership — the Harvester Writes, Agents Only Emit | 2026-08-25 |
| [ADR-035](ADR-035-fast-lane-closed-producer-roster.md) | Active | The Fast Lane's Producer Roster Becomes Data, But Stays Closed | 2026-08-25 |
| [ADR-036](ADR-036-documentation-dispatch-caller-boundary.md) | Active | Documentation Dispatch Is Caller-Dependent — documentation-expert Is a Human Entry Point, Never an AC's assigned_agent | 2026-08-26 |
| [ADR-037](ADR-037-whole-collection-uniqueness-pass.md) | Active | Whole-Collection Uniqueness Pass — Verdict-Object Contract and Decision-Namespace Guard Registration | 2026-08-18 |
