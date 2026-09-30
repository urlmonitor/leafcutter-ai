---
title: "Kernel bootstrap runtime V0 (Stage 0 + Stage 1 MVP)"
status: in_progress
components:
  - decision_kernel
created: 2026-09-30
depends_on: []
priority: high
roadmap_phase: phase_kernel_1_founding
requires_diagram: true
requires_adr: true
change_target: code
risk_surface: privacy
tags:
  - decision-kernel
  - langgraph
  - jev
  - langfuse
  - umbrella
last_updated: 2026-09-30
files_touched:
  - requirements-dev.txt
  - docs/components.json
  - kernel/__init__.py
  - docs/architecture/components/decision-kernel.md
  - docs/analysis/2026-09-30-decision-kernel-design.md
  - docs/analysis/2026-09-30-decision-kernel-design-2-contracts-registry-config.md
  - docs/analysis/2026-09-30-decision-kernel-design-3-kernel-scheduler.md
  - docs/analysis/2026-09-30-decision-kernel-design-4-jev-and-capabilities.md
  - docs/analysis/2026-09-30-decision-kernel-design-5-client-observability.md
  - docs/analysis/2026-09-30-decision-kernel-design-6-tests-phases-risks.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-2-runtime-and-registry.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-3-contracts.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-4-scheduler-jev-capabilities.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-5-client-observability-safeguards.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-6-gaps-build-verification.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-7-later-stages.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-8-audit-links-handoff.md
  - tickets/00_inbox/TICKET-20260930-KernelBootstrapV0.md
agents:
  commit: signed_off
---

# Kernel bootstrap runtime V0 (Stage 0 + Stage 1 MVP)

## Actor / Goal
In order to answer engineering decision and research questions with evidence instead of
one large prompt, we need a small, resumable LangGraph decision kernel inside leafcutter-ai
— Jev for bounded judgments, native decision and research capabilities, one real read-only
retrieval adapter, cooperative Claude Code handoff, capability-gap records and Langfuse
tracing — so that `/leafcutter <goal>` returns an evidence-backed, traceable result.

## Context
- **Specification (source of truth):** Revision 3, 30 September 2026, copied in-tree as
  [part 1](../../docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3.md) to
  [part 8](../../docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-8-audit-links-handoff.md).
  It supersedes the earlier V0 specification. Scope is **Stage 0 and Stage 1 MVP only**;
  Stages 2-5 are preserved as extension points, not built.
- **Design (implementation plan for all phases):**
  [docs/analysis/2026-09-30-decision-kernel-design.md](../../docs/analysis/2026-09-30-decision-kernel-design.md)
  and its parts 2-6; component overview in
  [docs/architecture/components/decision-kernel.md](../../docs/architecture/components/decision-kernel.md).
- **Binding user decisions (2026-09-30):**
  1. This umbrella ticket exists to satisfy the ticket mandate. It carries **no acceptance
     criteria** and does not go through `/plan-feature`.
  2. The kernel lives in leafcutter-ai only. It is not shipped to adopter projects: no
     `templates/` source, no `build.py` deploy registration, no `package_boundary` entry.
  3. A **new capability registry** (`config/capability_registry.json` plus schema) that starts
     empty. Legacy registries (agents, skills, workflows, commands) are never normalized or
     routed over. A legacy asset may be admitted only by an explicit, recorded admission
     decision. This deliberately deviates from spec §2.1(3) and §6; see the design, part 2.
  4. Langfuse Cloud through `.env` keys (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`,
     `LANGFUSE_BASE_URL`). Tests use a no-op/recording tracer.
  5. Live Jev calls, including repository excerpts, are approved for smoke tests and the
     dogfood run. Unit tests always use the deterministic Jev double.
  6. Latest LangGraph plus the Langfuse SDK, the sqlite checkpointer and `langchain-typesafe`,
     pinned in `requirements-dev.txt`.
  7. Claude Code client per spec §11: project skill plus CLI `run|resume|status|cancel --json`
     with cooperative, checkpointed host handoff.

## Scope of this ticket
All implementation phases P1-P10 in the design's phase plan (design part 6), in spec §15.2
order. Phase 0 (this commit) delivers the Stage 0 mapping, live Jev and Langfuse smoke
evidence, pinned dependencies, the component registration and the design.

## Out of Scope
- Stages 2-5 of the specification.
- Shipping any kernel artifact to adopters.
- Renaming or replacing the existing `/leafcutter` knowledge-hub command. That is an open
  user decision (design part 5).
- Writing the workflow-representation ADR. That is the dogfood output after the MVP runs.

## Risk & Safety
- Touches money? Only third-party API usage: Jev is billed per input token, and Langfuse
  Cloud usage applies. Call caps bound both.
- Touches data? Repository excerpts are sent to Jev and Langfuse under the configured data
  policy, with redaction. Runtime writes are limited to the gitignored run directory
  `.leafcutter/kernel/`.
- Reversibility? Fully reversible. The kernel is a new, self-contained package with no
  changes to existing runtime code paths.

## Comments

_(Append-only log — leave blank when authoring.)_

### 2026-09-30 12:00 — commit (status: ok)
feedback-id: fb_2026-09-30_29582173
Auto-authorized commit gate: subject "chore(kernel): add Phase 0 design, Rev 3 spec and dependency pins"; staged files: docs/INDEX.md docs/analysis/2026-09-30-decision-kernel-design-2-contracts-registry-config.md docs/analysis/2026-09-30-decision-kernel-design-3-kernel-scheduler.md docs/analysis/2026-09-30-decision-kernel-design-4-jev-and-capabilities.md docs/analysis/2026-09-30-decision-kernel-design-5-client-observability.md docs/analysis/2026-09-30-decision-kernel-design-6-tests-phases-risks.md docs/analysis/2026-09-30-decision-kernel-design.md docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-2-runtime-and-registry.md docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-3-contracts.md docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-4-scheduler-jev-capabilities.md docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-5-client-observability-safeguards.md docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-6-gaps-build-verification.md docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-7-later-stages.md docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-8-audit-links-handoff.md docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3.md docs/architecture/components/decision-kernel.md docs/components.json leafcutter_kernel/__init__.py requirements-dev.txt tickets/00_inbox/TICKET-20260930-KernelBootstrapV0.md 
