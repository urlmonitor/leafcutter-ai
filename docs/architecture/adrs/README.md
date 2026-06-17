---
title: "Architecture Decision Records"
description: "Index of all Architecture Decision Records (ADRs) for the leafcutter-ai package, listing each decision's number, status, title, and date."
type: "reference"
---

# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for the leafcutter-ai
package. ADRs document significant architectural decisions — the context, the choice
made, and the consequences — so that future contributors can understand *why* things
are the way they are.

## Index

| # | Status | Title | Date |
|---|--------|-------|------|
| [ADR-001](ADR-001-self-hosting-boundary.md) | Accepted | Self-Hosting Boundary — Config-Driven Path Resolution | 2026-05-19 |
| [ADR-002](ADR-002-dual-platform-compilation.md) | Active | Dual Platform Compilation for AI Agents | 2026-05-22 |
| [ADR-003](ADR-003-test-source-of-truth-discipline.md) | Accepted | Tests Are Mirrors of Production Contracts — Contract Shrinkage Requires Authorization | 2026-05-22 |
| [ADR-004](ADR-004-consolidated-output-root.md) | Active | Consolidated Output Root — All build.py Artifacts Under .leafcutter/ | 2026-05-27 |
| [ADR-004b](ADR-004-tdd-workflow-enforcement.md) | Active | Test-First Workflow Enforcement in the Agentic Build Pipeline | 2026-05-27 |
| [ADR-005](ADR-005-frontend-coder-agent.md) | Active | frontend-coder as a First-Class Sibling Implementation Agent | 2026-05-28 |
| [ADR-006](ADR-006-flatten-supervisor-chain.md) | Accepted | Flatten the Supervisor Chain — ticket-supervisor at Depth 0 | 2026-05-29 |
| [ADR-007](ADR-007-contract-driven-acs.md) | Accepted | Contract-Driven Acceptance Criteria | 2026-06-04 |
| [ADR-007b](ADR-007-ac-store-schema-id-format-enforcement.md) | Accepted | AC Store — YAML Schema, ID Format, and Bidirectional Enforcement Model | 2026-06-04 |
| [ADR-007c](ADR-007-test-fixture-convention.md) | Active | Test Fixture Convention | 2026-06-04 |
| [ADR-009](ADR-009-itpo-no-source-code-access.md) | Accepted | IT Product Owner v3 — Source Code Access Restriction | 2026-06-05 |
| [ADR-010](ADR-010-ac-store-as-authoritative-backlog.md) | Accepted | AC Store as Authoritative Backlog — Source-of-Truth Inversion | 2026-06-05 |
| [ADR-011](ADR-011-learning-emission-sink.md) | Active | Learning Emission Sink — Separate knowledge_emissions.jsonl vs Reuse agent_telemetry.jsonl | 2026-06-05 |
| [ADR-012](ADR-012-retire-create-ticket-js.md) | Accepted | Retire create-ticket.js — /plan-feature + /build-ac as Canonical Ticket-Creation Path | 2026-06-16 |
