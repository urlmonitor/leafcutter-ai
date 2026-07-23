---
title: "Documentation Index"
type: reference
status: active
created: 2026-06-30
last_updated: 2026-06-30
components: []
description: "Auto-generated index of all documentation files in the docs/ directory."
---

# Documentation Index

> **Auto-generated — do not edit manually.**
> Run `python scripts/generate_doc_index.py` to regenerate.
>
> Generated: 2026-07-23 07:08 UTC

This index lists every documentation file in the project.  BA and IT PO agents
should read this index first, identify which docs are relevant to the current
task, then pull only those files.

## Components

| Name | Path | Description |
|------|------|-------------|
| ac driven dev | [docs/architecture/components/ac-driven-dev.md](docs/architecture/components/ac-driven-dev.md) | The AC-driven development pipeline: /plan-feature authoring, /build-ac selection and ticket generation, and the AC-first build loop that treats the AC store as the authoritative backlog. |
| agent registry | [docs/architecture/components/agent-registry.md](docs/architecture/components/agent-registry.md) | Central registry of all phase agents with is_ticket_phase flags, produces traits, and model tier assignments used by ticket-supervisor for dispatch and validation. |
| agent telemetry | [docs/architecture/components/agent-telemetry.md](docs/architecture/components/agent-telemetry.md) | Event emission and tracking system for recording supervisor dispatch, agent sign-offs, retries, and failure events to JSONL logs for retrospective analysis. |
| bootstrap installer | [docs/architecture/components/bootstrap-installer.md](docs/architecture/components/bootstrap-installer.md) | Self-hosting installation system that deploys leafcutter-ai agents, skills, hooks, and config scaffolds into consumer projects with zero manual setup. |
| build epic workflow dispatch | [docs/architecture/components/build-epic-workflow-dispatch.md](docs/architecture/components/build-epic-workflow-dispatch.md) | build-epic.js Workflow Dispatch — Agent Flow |
| build orchestration | [docs/architecture/components/build-orchestration.md](docs/architecture/components/build-orchestration.md) | Build orchestration: pre-dispatch sequencing gates, dependency-cycle detection, parallelism limits, file-conflict isolation, and pre-drive reachability checks. |
| build ticket workflow dispatch | [docs/architecture/components/build-ticket-workflow-dispatch.md](docs/architecture/components/build-ticket-workflow-dispatch.md) | build-ticket.js Workflow Dispatch — Agent Flow |
| changelog | [docs/architecture/components/changelog.md](docs/architecture/components/changelog.md) | Automated changelog entry management system that tracks feature delivery history with structured YAML entries linked to tickets and commits. |
| commit guardian | [docs/architecture/components/commit-guardian.md](docs/architecture/components/commit-guardian.md) | Pre-commit hook orchestration system that enforces code quality, ADR coverage, component integrity, and structural rules before every commit lands. |
| doc compliance | [docs/architecture/components/doc-compliance.md](docs/architecture/components/doc-compliance.md) | Documentation compliance verification system that enforces frontmatter presence, description fields, doc-length limits, and coverage requirements across all project documentation. |
| feedback collector | [docs/architecture/components/feedback-collector.md](docs/architecture/components/feedback-collector.md) | Structured feedback collection system that aggregates agent quality signals into JSONL logs for retrospective analysis and continuous improvement. |
| finalize | [docs/architecture/components/finalize.md](docs/architecture/components/finalize.md) | The finalize-feature workflow: pre-merge test baseline capture, PR merge gating, push-before-merge sync, main sync, and ticket/epic closure. |
| glossary | [docs/architecture/components/glossary.md](docs/architecture/components/glossary.md) | Project terminology registry with automated coverage checks that ensure novel jargon is triaged and documented consistently across all project artifacts. |
| injection builder | [docs/architecture/components/injection-builder.md](docs/architecture/components/injection-builder.md) | Context injection payload assembler that delivers structured knowledge to agents at invocation time via the 11-channel agent knowledge plane. |
| knowledge management | [docs/architecture/components/knowledge-management.md](docs/architecture/components/knowledge-management.md) | The cross-surface knowledge graph: surface ingestion from config/paths.json, node/edge derivation, AC-to-code traceability, the query layer, and graph visualisation. |
| knowledge system | [docs/architecture/components/knowledge-system.md](docs/architecture/components/knowledge-system.md) | Knowledge harvesting and context file maintenance system that persists learnings across agent sessions for improved future-invocation quality. |
| persona management | [docs/architecture/components/persona-management.md](docs/architecture/components/persona-management.md) | Persona definitions, AC targeting by persona, and persona knowledge-graph queries. |
| release manager | [docs/architecture/components/release-manager.md](docs/architecture/components/release-manager.md) | Semantic version computation and schema diff checking system for managing structured releases of the leafcutter-ai package. |
| roadmap | [docs/architecture/components/roadmap.md](docs/architecture/components/roadmap.md) | Phase-based roadmap that tracks current outcomes, exit criteria, and the tickets advancing each outcome toward the stable MVP target. |
| skill registry | [docs/architecture/components/skill-registry.md](docs/architecture/components/skill-registry.md) | Registry of all available skills with metadata on usage context, allowed tools, and configuration constraints for agent invocation. |
| stakeholder delivery | [docs/architecture/components/stakeholder-delivery.md](docs/architecture/components/stakeholder-delivery.md) | Stakeholder-facing delivery of product value: a presentation agent that renders approved value propositions into self-contained HTML decks and tailored stakeholder communications. |
| supervisor spawn topology | [docs/architecture/components/supervisor-spawn-topology.md](docs/architecture/components/supervisor-spawn-topology.md) | Supervisor Spawn Topology — Flattened Agent Dispatch Chain |
| template compiler | [docs/architecture/components/template-compiler.md](docs/architecture/components/template-compiler.md) | Build-time template compilation system that transforms Jinja-style agent and skill templates into deployed artifacts during the leafcutter build phase. |
| ticket lifecycle | [docs/architecture/components/ticket-lifecycle.md](docs/architecture/components/ticket-lifecycle.md) | End-to-end ticket management system covering inbox creation, status transitions, phase-agent sign-offs, and archival to the done state. |
| ux prototyping | [docs/architecture/components/ux-prototyping.md](docs/architecture/components/ux-prototyping.md) | The flow-first upstream authoring surface: a schema-validated store of Flows, Mockups, and Mock Data that captures product intent, generates acceptance criteria, and is rendered live by the Leafcutter Atlas. |
| worktree manager | [docs/architecture/components/worktree-manager.md](docs/architecture/components/worktree-manager.md) | Git worktree lifecycle management component that creates, tracks, and tears down isolated branch environments for parallel epic and ticket development. |
| worktree quality gate guard | [docs/architecture/components/worktree-quality-gate-guard.md](docs/architecture/components/worktree-quality-gate-guard.md) | Container-level overview of the worktree quality-gate guard subsystem: the four-check probe, the index-0 self-healing config hook, and the three lifecycle gates that keep pre-commit hooks firing inside git worktrees. |

## Architecture Diagrams

| Name | Path | Description |
|------|------|-------------|
| agent delivery workflows | [docs/architecture/agent_delivery_workflows.md](docs/architecture/agent_delivery_workflows.md) | Visualises how the leafcutter-ai agent ecosystem orchestrates code delivery — slash-command entry points, supervisor dispatch topology, quick-fix workflow, and blocker adjudication flows. |
| agent knowledge plane | [docs/architecture/agent_knowledge_plane.md](docs/architecture/agent_knowledge_plane.md) | Canonical reference for knowledge injection — all channels through which agents receive context at invocation time, including skills_invoked cross-reference validation. |
| agent knowledge system | [docs/architecture/agent_knowledge_system.md](docs/architecture/agent_knowledge_system.md) | Agent Knowledge System |
| feedback lifecycle | [docs/architecture/feedback-lifecycle.md](docs/architecture/feedback-lifecycle.md) | Feedback Lifecycle — Data Flow |

## Architecture Decision Records (ADRs)

| Name | Path | Description |
|------|------|-------------|
| ADR 001 self hosting boundary | [docs/architecture/adrs/ADR-001-self-hosting-boundary.md](docs/architecture/adrs/ADR-001-self-hosting-boundary.md) | Documents the self-hosting boundary for leafcutter-ai — config-driven path resolution, build output separation, and user-curated PROJECT_CONTEXT.md preservation across upgrades. |
| ADR 002 dual platform compilation | [docs/architecture/adrs/ADR-002-dual-platform-compilation.md](docs/architecture/adrs/ADR-002-dual-platform-compilation.md) | ADR-002: Dual Platform Compilation for AI Agents |
| ADR 003 test source of truth discipline | [docs/architecture/adrs/ADR-003-test-source-of-truth-discipline.md](docs/architecture/adrs/ADR-003-test-source-of-truth-discipline.md) | Accepted (2026-05-22) |
| ADR 004 consolidated output root | [docs/architecture/adrs/ADR-004-consolidated-output-root.md](docs/architecture/adrs/ADR-004-consolidated-output-root.md) | Accepted (2026-05-27) |
| ADR 004 tdd workflow enforcement | [docs/architecture/adrs/ADR-004-tdd-workflow-enforcement.md](docs/architecture/adrs/ADR-004-tdd-workflow-enforcement.md) | Accepted (2026-05-27) |
| ADR 005 frontend coder agent | [docs/architecture/adrs/ADR-005-frontend-coder-agent.md](docs/architecture/adrs/ADR-005-frontend-coder-agent.md) | Decides to add frontend-coder as a sibling implementation agent alongside python-coder and sql-coder, dispatched directly by ticket-supervisor. |
| ADR 006 flatten supervisor chain | [docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md](docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md) | Architectural decision to flatten the supervisor chain so ticket-supervisor runs at depth 0 and phase agents at depth 1, satisfying Claude Code's hard depth-1 Agent-tool nesting limit. |
| ADR 007 ac store schema id format enforcement | [docs/architecture/adrs/ADR-007-ac-store-schema-id-format-enforcement.md](docs/architecture/adrs/ADR-007-ac-store-schema-id-format-enforcement.md) | Defines the AC YAML schema, hierarchical ID format with parent derivation algorithm, status lifecycle, and stdlib-only commit-time enforcement model for the leafcutter AC Traceability Store. |
| ADR 007 contract driven acs | [docs/architecture/adrs/ADR-007-contract-driven-acs.md](docs/architecture/adrs/ADR-007-contract-driven-acs.md) | ADR-007: Contract-Driven Acceptance Criteria |
| ADR 007 test fixture convention | [docs/architecture/adrs/ADR-007-test-fixture-convention.md](docs/architecture/adrs/ADR-007-test-fixture-convention.md) | Test Fixture Convention: load_fixture() Helper and tests/fixtures/ Directory Layout |
| ADR 009 itpo no source code access | [docs/architecture/adrs/ADR-009-itpo-no-source-code-access.md](docs/architecture/adrs/ADR-009-itpo-no-source-code-access.md) | ADR-009: IT Product Owner v3 — Source Code Access Restriction |
| ADR 010 ac store as authoritative backlog | [docs/architecture/adrs/ADR-010-ac-store-as-authoritative-backlog.md](docs/architecture/adrs/ADR-010-ac-store-as-authoritative-backlog.md) | Records the decision to treat the AC YAML store as the single source of truth for the product backlog, inverting the traditional ticket-first model. Covers staged-commit model and partial-run recovery. |
| ADR 011 learning emission sink | [docs/architecture/adrs/ADR-011-learning-emission-sink.md](docs/architecture/adrs/ADR-011-learning-emission-sink.md) | ADR-011: Learning Emission Sink — Separate knowledge_emissions.jsonl vs Reuse agent_telemetry.jsonl |
| ADR 012 retire create ticket js | [docs/architecture/adrs/ADR-012-retire-create-ticket-js.md](docs/architecture/adrs/ADR-012-retire-create-ticket-js.md) | Decision to retire the create-ticket.js workflow via a runtime guard and adopt /plan-feature + /build-ac as the canonical ticket-creation path. |
| ADR 013 portable skill script deployment boundary | [docs/architecture/adrs/ADR-013-portable-skill-script-deployment-boundary.md](docs/architecture/adrs/ADR-013-portable-skill-script-deployment-boundary.md) | Establishes that a skill is portable: true iff its SKILL.md and all referenced scripts deploy to consumer installs, and adds build_ac_store() to deploy the AC-pipeline scripts accordingly. |
| ADR 014 exception guard enforcement scope | [docs/architecture/adrs/ADR-014-exception-guard-enforcement-scope.md](docs/architecture/adrs/ADR-014-exception-guard-enforcement-scope.md) | Records two enforcement-scope decisions for the exception-handling pre-commit guard: subprocess calls become a mandatory I/O boundary (GE-108a), and only WARNING-or-higher logging on a real logger clears a blind-catch handler (GE-108b). |
| ADR 015 guard honors noqa ble001 | [docs/architecture/adrs/ADR-015-guard-honors-noqa-ble001.md](docs/architecture/adrs/ADR-015-guard-honors-noqa-ble001.md) | Records the decision to teach check_exception_handling.py to honor inline `# noqa: BLE001` suppression comments, scoped per-line and per-violation-code to match Ruff semantics, resolving the GE-108b self-hosting regression where the widened guard flagged leafcutter's own intentionally-blind handlers. |
| ADR 016 ci fresh clone test dependencies | [docs/architecture/adrs/ADR-016-ci-fresh-clone-test-dependencies.md](docs/architecture/adrs/ADR-016-ci-fresh-clone-test-dependencies.md) | Records the decision to extend install_shims() with script-directory shims so that the full test suite passes on a fresh clone after the ADR-004 consolidation removed scripts/commit_guardian/, scripts/doc_compliance/, and scripts/feedback/ from the project root. Also records the decision to move feedback scripts into templates/scripts/feedback/ as the canonical tracked source so that build.py's _check_script_reference_guard() passes on a fresh clone (AC BP-1200a-1-ii). |
| ADR 017 computed quality gates | [docs/architecture/adrs/ADR-017-computed-quality-gates.md](docs/architecture/adrs/ADR-017-computed-quality-gates.md) | Two-axis classification system (change_target x risk_surface) that maps ticket changes to mandatory guardrail agents at ticket-creation time. |
| ADR 017 dual engine workflow support | [docs/architecture/adrs/ADR-017-dual-engine-workflow-support.md](docs/architecture/adrs/ADR-017-dual-engine-workflow-support.md) | Records the decision to author all new workflow scripts exclusively in E2 top-level-body form, generate E1-compatible shim wrappers at build time, use a runtime engine-detection predicate to route execution, and explicitly fail on unrecognised engines rather than fall back to LLM. Establishes the canonical E2 authoring contract based on empirical probes of the Claude Code 2.1.185 workflow engine. |
| ADR 017 worktree quality gate guard | [docs/architecture/adrs/ADR-017-worktree-quality-gate-guard.md](docs/architecture/adrs/ADR-017-worktree-quality-gate-guard.md) | Records the design of the worktree quality gate guard: a four-check probe model (binary, config, git_hook, canary) whose canary check requires the hook chain to actually FIRE, a fail-closed-on-self-error invariant with no fail-open path, an index-0 self-healing hook that re-materialises the pre-commit config, dual create-time and pre-drive gates, template/deployed source parity per ADR-001, and supersession of the interim one-file feature/SKILL.md slice (commit 586d6191). Motivated by the fresh-worktree silent-skip failure mode surfaced in the EPIC-AcPipelineDeployGaps retrospective. |
| ADR 018 agent isolation topology | [docs/architecture/adrs/ADR-018-agent-isolation-topology.md](docs/architecture/adrs/ADR-018-agent-isolation-topology.md) | Records the decision to isolate each parallel coding-agent drive in its own independent git clone (own object store) instead of a git worktree sharing one .git, to make main structurally unmodifiable except through a gated PR + merge-queue workflow on an authoritative hub, and to cap agents-per-feature (not features-in-flight). Motivated by repeated 0-byte-object / poisoned-index corruption of the shared .git under ~16 concurrent autonomous committers, and by 2025-2026 research showing every SOTA autonomous-agent product isolates each agent's checkout+object-store and integrates via PR. Includes a worktree-agent -> clone-agent migration plan and the impact on the in-flight BO-1600 guardrail ACs. |
| ADR 019 build feature inline phase dispatch | [docs/architecture/adrs/ADR-019-build-feature-inline-phase-dispatch.md](docs/architecture/adrs/ADR-019-build-feature-inline-phase-dispatch.md) | Records the decision to inline the driveTicketPhases loop from build-ticket.js directly into build-feature.js, replacing the prior pattern of dispatching a ticket-supervisor agent per ticket. The prior pattern silently placed phase agents at depth 2 — beyond Claude Code's hard depth-1 Agent-tool nesting limit — so no phase templates ever applied. The workflow() alternative is also prohibited by the E2 leaf-invariant. Inlining the loop is the only configuration that satisfies both constraints. |
| ADR 020 live surface tester | [docs/architecture/adrs/ADR-020-live-surface-tester.md](docs/architecture/adrs/ADR-020-live-surface-tester.md) | Overview of ADR-020: Live Surface Tester — Port Registry, Read-Only |
| ADR 021 plan feature product truth phase | [docs/architecture/adrs/ADR-021-plan-feature-product-truth-phase.md](docs/architecture/adrs/ADR-021-plan-feature-product-truth-phase.md) | Records the decision to wire the product-truth authoring agents (pt-classifier, mock-data-author, mockup-author, flow-author) into the /plan-feature workflow as an always-on phase between ac-triage and the AC pipeline. The classifier runs on every invocation and its outcome derives the run-set; artifact agents run in a fixed order behind per-stage approve/edit/cancel gates with surgical, commit-before-next commits; the approved flow is handed to the business-analyst and its reported flow_backlinks are reconciled into step.implements by apply_flow_backlinks.py; and the phase self-skips non-silently when the product-truth store is absent. Realises the flow-first authoring surface of ADR-023. |
| ADR 022 mockups are the real app in mock mode | [docs/architecture/adrs/ADR-022-mockups-are-the-real-app-in-mock-mode.md](docs/architecture/adrs/ADR-022-mockups-are-the-real-app-in-mock-mode.md) | Records the now-decided model for how product-truth mockups work: a mockup is NOT standalone HTML and is NOT an isolated /mockups preview component — it is the REAL application running in MOCK MODE (same stack, same routes/components, data swapped to mock, toggled on, deployed to a shareable dev URL for review). Two flavors under one mock-mode concept: UI-heavy (a data-layer mock PROVIDER returns product-truth mock-data records, no DB) and DB-heavy (the mock-data artifact is a TYPED DATA MODEL plus seed rows that seeds a THROWAWAY instance of the project's REAL DB engine — Postgres / MSSQL / Neo4j — so the schema itself can be prototyped on the real running site before any migration exists). The mock-data artifact thus becomes the schema prototype that feeds forward on approval: sql-coder builds the real schema from the typed model, test-writer seeds fixtures from the seed rows, frontend-coder hardens the mock-mode screens, user-surface-smoker asserts the built screen matches the approved mock-mode screen. Extends ADR-023 and supersedes the interim bespoke-HTML and isolated-/mockups-preview-component approaches (draft-only, never merged). |
| ADR 023 product truth flow first upstream layer | [docs/architecture/adrs/ADR-023-product-truth-flow-first-upstream-layer.md](docs/architecture/adrs/ADR-023-product-truth-flow-first-upstream-layer.md) | Records the decision to introduce a second structured store — the product-truth store (flows, mockups, mock data) — as the flow-first upstream authoring surface that GENERATES acceptance criteria, while the AC store remains the single authoritative backlog. Reconciles ADR-010 by scoping the AC store's authority to the backlog and positioning flows as the upstream product-intent surface. Covers flow-first authoring, ACs derived from flow steps, derived impl_status rolled up from work_status, and the Leafcutter Atlas as the read surface. |

## How-To Guides

| Name | Path | Description |
|------|------|-------------|
| ac driven build loop | [docs/how-to/ac-driven-build-loop.md](docs/how-to/ac-driven-build-loop.md) | Step-by-step guide to running the AC-driven build loop (/build-ac and ac-scanner) on a consumer install, including the deployed ac_store scripts. |
| ac driven development | [docs/how-to/ac-driven-development.md](docs/how-to/ac-driven-development.md) | How to use the AC-driven development system |
| ac traceability store | [docs/how-to/ac-traceability-store.md](docs/how-to/ac-traceability-store.md) | How-to guide for delivering approved ACs via the reviewed-PR path, and for creating, amending, deprecating, and tracing acceptance criteria through the AC Traceability Store and knowledge map. |
| approval gate | [docs/how-to/approval-gate.md](docs/how-to/approval-gate.md) | Task-oriented guide: read the readiness report, choose a gate option (yes / review-all / cancel), and manage the IT PO review-all path. |
| authoring product truth artifacts | [docs/how-to/authoring-product-truth-artifacts.md](docs/how-to/authoring-product-truth-artifacts.md) | Step-by-step guide for authoring product-truth artifacts by hand, including the mandatory search-index.json then add-vs-create protocol that keeps exactly one canonical dataset per entity per component. |
| build ac unified | [docs/how-to/build-ac-unified.md](docs/how-to/build-ac-unified.md) | Task-oriented guide: /build-ac auto-detects leaf vs goal mode — leaf ACs generate a single ticket, goal ACs generate a full EPIC folder. |
| configure workflow allowlist | [docs/how-to/configure-workflow-allowlist.md](docs/how-to/configure-workflow-allowlist.md) | How to configure the workflow shell-command allowlist |
| creating a claude code hook | [docs/how-to/creating-a-claude-code-hook.md](docs/how-to/creating-a-claude-code-hook.md) | How to create a Claude Code hook |
| creating a skill | [docs/how-to/creating-a-skill.md](docs/how-to/creating-a-skill.md) | How to create a skill |
| creating an agent template | [docs/how-to/creating-an-agent-template.md](docs/how-to/creating-an-agent-template.md) | How to create an agent template |
| declare a knowledge surface | [docs/how-to/declare-a-knowledge-surface.md](docs/how-to/declare-a-knowledge-surface.md) | Step-by-step guide for registering a new source of knowledge in config/paths.json so it participates in the cross-surface knowledge map. |
| declare component membership | [docs/how-to/declare-component-membership.md](docs/how-to/declare-component-membership.md) | Step-by-step guide for adding a components list to a knowledge item so it joins the cross-surface component view, and for querying a component back to its criteria, source files, and tests. |
| deprecating or removing artifacts | [docs/how-to/deprecating-or-removing-artifacts.md](docs/how-to/deprecating-or-removing-artifacts.md) | Step-by-step guide for safely deprecating or deleting agents, skills, hooks, and scripts from the leafcutter package without breaking consumer builds. |
| drain backlog with build backlog | [docs/how-to/drain-backlog-with-build-backlog.md](docs/how-to/drain-backlog-with-build-backlog.md) | How to drain the backlog automatically with /build-backlog |
| drive epic manually | [docs/how-to/drive-epic-manually.md](docs/how-to/drive-epic-manually.md) | How to drive an epic manually when epic-supervisor is unavailable |
| finalize feature | [docs/how-to/finalize-feature.md](docs/how-to/finalize-feature.md) | Step-by-step guide for running /finalize-feature to merge a feature branch, |
| goal to epic | [docs/how-to/goal-to-epic.md](docs/how-to/goal-to-epic.md) | Task-oriented guide: invoke /build-ac with a goal-level AC ID to generate a full EPIC folder of tickets in one command. |
| inject project knowledge into agents | [docs/how-to/inject-project-knowledge-into-agents.md](docs/how-to/inject-project-knowledge-into-agents.md) | How to inject project knowledge into a portable agent |
| known failing tests baseline | [docs/how-to/known-failing-tests-baseline.md](docs/how-to/known-failing-tests-baseline.md) | How to Use the Known-Failing Tests Baseline |
| managing pre commit hooks | [docs/how-to/managing-pre-commit-hooks.md](docs/how-to/managing-pre-commit-hooks.md) | Step-by-step guide for enabling, disabling, configuring, and opt-ing in to pre-commit hooks in the leafcutter commit_guardian system. |
| adopt consolidated output root | [docs/how-to/output-layout/adopt-consolidated-output-root.md](docs/how-to/output-layout/adopt-consolidated-output-root.md) | How to adopt the consolidated output root (.leafcutter/) |
| product truth schema reference | [docs/how-to/product-truth-schema-reference.md](docs/how-to/product-truth-schema-reference.md) | Field-by-field reference for the four product-truth schemas — Flow, Mock Data, Mockup, and Classifier eval — including required fields, enums, id patterns, and which fields are authored vs derived. |
| ticket creation workflow | [docs/how-to/ticket-creation-workflow.md](docs/how-to/ticket-creation-workflow.md) | Guide to the canonical ticket-creation workflow (/plan-feature then /build-ac) that replaced the retired create-ticket.js, with a migration note. |
| upgrade frontend coder unified agent | [docs/how-to/upgrade-frontend-coder-unified-agent.md](docs/how-to/upgrade-frontend-coder-unified-agent.md) | Step-by-step guide for adopters migrating from the separate frontend-coder and frontend-design split to the unified frontend-coder agent — covers what build.py does automatically, verification steps, and rollback instructions. |
| using frontend coder with design integration | [docs/how-to/using-frontend-coder-with-design-integration.md](docs/how-to/using-frontend-coder-with-design-integration.md) | How to use frontend-coder with design integration |
| verify precommit active | [docs/how-to/verify-precommit-active.md](docs/how-to/verify-precommit-active.md) | Step-by-step guide to running the verify_precommit_active.py probe and interpreting its four checks to confirm that pre-commit hooks will fire in a git worktree. |
| working with leafcutter | [docs/how-to/working-with-leafcutter.md](docs/how-to/working-with-leafcutter.md) | How to work with leafcutter end-to-end |
| writing a tdd ticket | [docs/how-to/writing-a-tdd-ticket.md](docs/how-to/writing-a-tdd-ticket.md) | This guide walks you through writing a ticket that will go through the leafcutter |

## Reference

| Name | Path | Description |
|------|------|-------------|
| ac schema | [docs/reference/ac-schema.md](docs/reference/ac-schema.md) | Field-by-field reference for AC YAML files, the hierarchical ID format and parent derivation algorithm, status lifecycle, and pre-commit hooks that enforce the AC store at commit time. |
| agent teams constraints | [docs/reference/agent-teams-constraints.md](docs/reference/agent-teams-constraints.md) | Reference: Claude Code Agent Teams Constraints |
| agent template frontmatter | [docs/reference/agent-template-frontmatter.md](docs/reference/agent-template-frontmatter.md) | Reference: Agent Template Frontmatter Fields |
| claude code hooks | [docs/reference/claude-code-hooks.md](docs/reference/claude-code-hooks.md) | Reference guide for Claude Code PreToolUse and PostToolUse hooks — hook types, registration format, exit-code contract, and the fail-open convention. |
| feedback concurrency | [docs/reference/feedback-concurrency.md](docs/reference/feedback-concurrency.md) | Reference: Feedback Client Concurrency Limitation |
| frontend coder capabilities | [docs/reference/frontend-coder-capabilities.md](docs/reference/frontend-coder-capabilities.md) | frontend-coder Unified Agent — Preserved Capabilities Reference |
| skill frontmatter | [docs/reference/skill-frontmatter.md](docs/reference/skill-frontmatter.md) | Reference: SKILL.md Frontmatter Fields |
| skills config fields | [docs/reference/skills-config-fields.md](docs/reference/skills-config-fields.md) | Overview of Reference: skills_config.json Fields. |
| workflow authoring contract | [docs/reference/workflow-authoring-contract.md](docs/reference/workflow-authoring-contract.md) | Copy-paste reference for workflow script authors covering the E2 canonical execution contract, E1-wrap shim pattern, primitive mapping table, and non-transparent edge handling conventions. |
| workflow constraints | [docs/reference/workflow-constraints.md](docs/reference/workflow-constraints.md) | Reference: Claude Code Workflow Script Constraints |

## Explanation

| Name | Path | Description |
|------|------|-------------|
| consolidated output root | [docs/explanation/consolidated-output-root.md](docs/explanation/consolidated-output-root.md) | The Consolidated Output Root |
| tdd workflow | [docs/explanation/tdd-workflow.md](docs/explanation/tdd-workflow.md) | This explanation describes how Test-Driven Development works inside leafcutter's |

## Conventions

| Name | Path | Description |
|------|------|-------------|
| PROJECT CONTEXT injection | [docs/conventions/PROJECT_CONTEXT-injection.md](docs/conventions/PROJECT_CONTEXT-injection.md) | Convention: PROJECT_CONTEXT Injection for Portable Agents |
| adr numbering | [docs/conventions/adr-numbering.md](docs/conventions/adr-numbering.md) | Convention: ADR Numbering and Collision Prevention |

## Retrospectives

| Name | Path | Description |
|------|------|-------------|
| 2026 05 22 epic antigravity support | [docs/retrospectives/2026-05-22-epic-antigravity-support.md](docs/retrospectives/2026-05-22-epic-antigravity-support.md) | Retrospective: Dual Platform Antigravity Support |
| EPIC ACDrivenDevelopment | [docs/retrospectives/EPIC-ACDrivenDevelopment.md](docs/retrospectives/EPIC-ACDrivenDevelopment.md) | Date: 2026-06-05 |
| EPIC ACTraceabilityStore | [docs/retrospectives/EPIC-ACTraceabilityStore.md](docs/retrospectives/EPIC-ACTraceabilityStore.md) | Date: 2026-06-04 |
| EPIC AcPatternEnforcementIsMechanically | [docs/retrospectives/EPIC-AcPatternEnforcementIsMechanically.md](docs/retrospectives/EPIC-AcPatternEnforcementIsMechanically.md) | Retrospective for EPIC-AcPatternEnforcementIsMechanically (ACS-500f) |
| EPIC AcPipelineDeployGaps | [docs/retrospectives/EPIC-AcPipelineDeployGaps.md](docs/retrospectives/EPIC-AcPipelineDeployGaps.md) | Post-merge retrospective for EPIC-AcPipelineDeployGaps (PR #88), covering six knowledge items on worktree setup, deployment AC assertions, test coverage, and epic close protocols. |
| EPIC BOPhantomDoneRemediation | [docs/retrospectives/EPIC-BOPhantomDoneRemediation.md](docs/retrospectives/EPIC-BOPhantomDoneRemediation.md) | Overview of Retrospective: EPIC-BOPhantomDoneRemediation. |
| EPIC CodeQualityHooks | [docs/retrospectives/EPIC-CodeQualityHooks.md](docs/retrospectives/EPIC-CodeQualityHooks.md) | Epic retrospective for EPIC-CodeQualityHooks — jscpd duplicate-code detection and diff-cover test-coverage enforcement hooks. |
| EPIC CompletionManifestSignoff | [docs/retrospectives/EPIC-CompletionManifestSignoff.md](docs/retrospectives/EPIC-CompletionManifestSignoff.md) | Date: 2026-05-30 |
| EPIC ComputedQualityGates | [docs/retrospectives/EPIC-ComputedQualityGates.md](docs/retrospectives/EPIC-ComputedQualityGates.md) | Post-merge retrospective for EPIC-ComputedQualityGates (PR #201), covering the phantom-done remediation, three-layer integration gap root cause analysis, backfill of 1,802 ACs, and five proposed knowledge items. |
| EPIC ErrorHandlingEnforcement | [docs/retrospectives/EPIC-ErrorHandlingEnforcement.md](docs/retrospectives/EPIC-ErrorHandlingEnforcement.md) | Date: 2026-06-01 |
| EPIC Exceptionhandlingguardenforcestheerror | [docs/retrospectives/EPIC-Exceptionhandlingguardenforcestheerror.md](docs/retrospectives/EPIC-Exceptionhandlingguardenforcestheerror.md) | Date: 2026-06-18 |
| EPIC FinalizeFeatureHardening | [docs/retrospectives/EPIC-FinalizeFeatureHardening.md](docs/retrospectives/EPIC-FinalizeFeatureHardening.md) | Retrospective: EPIC-FinalizeFeatureHardening |
| EPIC FlattenSupervisorChain | [docs/retrospectives/EPIC-FlattenSupervisorChain.md](docs/retrospectives/EPIC-FlattenSupervisorChain.md) | Date: 2026-05-29 |
| EPIC FrontendAgent | [docs/retrospectives/EPIC-FrontendAgent.md](docs/retrospectives/EPIC-FrontendAgent.md) | Date: 2026-05-28 |
| EPIC GoalToEpicLeafFilter | [docs/retrospectives/EPIC-GoalToEpicLeafFilter.md](docs/retrospectives/EPIC-GoalToEpicLeafFilter.md) | Epic retrospective for EPIC-GoalToEpicLeafFilter — leaf filter correctness fixes for scan_ac_store.py (done/superseded exclusion and out-of-scope cycle resilience). |
| EPIC MoveOnMainOnly | [docs/retrospectives/EPIC-MoveOnMainOnly.md](docs/retrospectives/EPIC-MoveOnMainOnly.md) | Date: 2026-06-03 |
| EPIC Oneagenthandlesboththelookandthecodefor | [docs/retrospectives/EPIC-Oneagenthandlesboththelookandthecodefor.md](docs/retrospectives/EPIC-Oneagenthandlesboththelookandthecodefor.md) | Retrospective for the frontend-coder/frontend-design unification epic (BP-700) |
| EPIC PhantomDoneFilesTouched | [docs/retrospectives/EPIC-PhantomDoneFilesTouched.md](docs/retrospectives/EPIC-PhantomDoneFilesTouched.md) | Epic retrospective for EPIC-PhantomDoneFilesTouched: real-format parser no-op, fail-open hole, AC audit, and finalize workflow bugs discovered during post-merge remediation. |
| EPIC PrecommitSafetyNet | [docs/retrospectives/EPIC-PrecommitSafetyNet.md](docs/retrospectives/EPIC-PrecommitSafetyNet.md) | Epic retrospective for EPIC-PrecommitSafetyNet — pre-commit safety net for the leafcutter-ai package. |
| EPIC QuickFixWorkflow | [docs/retrospectives/EPIC-QuickFixWorkflow.md](docs/retrospectives/EPIC-QuickFixWorkflow.md) | epic: EPIC-QuickFixWorkflow |
| EPIC SelfDescribingAgentsCorrections | [docs/retrospectives/EPIC-SelfDescribingAgentsCorrections.md](docs/retrospectives/EPIC-SelfDescribingAgentsCorrections.md) | Retrospective for EPIC-SelfDescribingAgentsCorrections |
| EPIC TDDWorkflowEnforcement | [docs/retrospectives/EPIC-TDDWorkflowEnforcement.md](docs/retrospectives/EPIC-TDDWorkflowEnforcement.md) | **Date**: 2026-05-27 |
| EPIC TrustworthyTestGate | [docs/retrospectives/EPIC-TrustworthyTestGate.md](docs/retrospectives/EPIC-TrustworthyTestGate.md) | Retrospective for EPIC-TrustworthyTestGate — AC-status-gated test enforcement gate (PR #172); 8 of 25 tickets completed. |
| TICKET 20260601 FixHooksDeploymentPipeline | [docs/retrospectives/TICKET-20260601-FixHooksDeploymentPipeline.md](docs/retrospectives/TICKET-20260601-FixHooksDeploymentPipeline.md) | Date: 2026-06-01 |
| TICKET 20260707 BP CollisionGuardrailAndDescriptiveSkills | [docs/retrospectives/TICKET-20260707-BP-CollisionGuardrailAndDescriptiveSkills.md](docs/retrospectives/TICKET-20260707-BP-CollisionGuardrailAndDescriptiveSkills.md) | Overview of Retrospective: BP-100m-1 + BP-1300a Build-Pipeline Remediation. |

## Glossary

- [docs/glossary.md](docs/glossary.md) — Authoritative glossary of leafcutter-ai project jargon and terminology,

---
*Index generated by `scripts/generate_doc_index.py`.*
