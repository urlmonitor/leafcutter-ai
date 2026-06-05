# Documentation Index

> **Auto-generated — do not edit manually.**
> Run `python scripts/generate_doc_index.py` to regenerate.
>
> Generated: 2026-06-05 12:16 UTC

This index lists every documentation file in the project.  BA and IT PO agents
should read this index first, identify which docs are relevant to the current
task, then pull only those files.

## Skills

| Name | Path | Description |
|------|------|-------------|
| knowledge-query | [templates/skills/knowledge-query/SKILL.md](templates/skills/knowledge-query/SKILL.md) | Cross-surface knowledge graph query. Invokes scripts/knowledge_query.py to search nodes across all paths.json surfaces. Supports keyword filter (--query), surface filter (--surface), JSON export (--format json), and edge list (--edges). |
| roadmap-query | [templates/skills/roadmap-query/SKILL.md](templates/skills/roadmap-query/SKILL.md) | Query ticket alignment against docs/roadmap.json. Lists tickets by phase, current-outcome filter, and unassigned warnings. |

## Components

| Name | Path | Description |
|------|------|-------------|
| build epic workflow dispatch | [docs/architecture/components/build-epic-workflow-dispatch.md](docs/architecture/components/build-epic-workflow-dispatch.md) | build-epic.js Workflow Dispatch — Agent Flow |
| build ticket workflow dispatch | [docs/architecture/components/build-ticket-workflow-dispatch.md](docs/architecture/components/build-ticket-workflow-dispatch.md) | build-ticket.js Workflow Dispatch — Agent Flow |
| supervisor spawn topology | [docs/architecture/components/supervisor-spawn-topology.md](docs/architecture/components/supervisor-spawn-topology.md) | Supervisor Spawn Topology — Flattened Agent Dispatch Chain |

## Architecture Diagrams

| Name | Path | Description |
|------|------|-------------|
| agent delivery workflows | [docs/architecture/agent_delivery_workflows.md](docs/architecture/agent_delivery_workflows.md) | Agent Code Delivery Workflows |
| agent knowledge plane | [docs/architecture/agent_knowledge_plane.md](docs/architecture/agent_knowledge_plane.md) | Agent Knowledge Plane |
| agent knowledge system | [docs/architecture/agent_knowledge_system.md](docs/architecture/agent_knowledge_system.md) | Agent Knowledge System |
| feedback lifecycle | [docs/architecture/feedback-lifecycle.md](docs/architecture/feedback-lifecycle.md) | Feedback Lifecycle — Data Flow |

## Architecture Decision Records (ADRs)

| Name | Path | Description |
|------|------|-------------|
| ADR 001 self hosting boundary | [docs/architecture/adrs/ADR-001-self-hosting-boundary.md](docs/architecture/adrs/ADR-001-self-hosting-boundary.md) | Accepted (2026-05-19) |
| ADR 002 dual platform compilation | [docs/architecture/adrs/ADR-002-dual-platform-compilation.md](docs/architecture/adrs/ADR-002-dual-platform-compilation.md) | ADR-002: Dual Platform Compilation for AI Agents |
| ADR 003 test source of truth discipline | [docs/architecture/adrs/ADR-003-test-source-of-truth-discipline.md](docs/architecture/adrs/ADR-003-test-source-of-truth-discipline.md) | Accepted (2026-05-22) |
| ADR 004 consolidated output root | [docs/architecture/adrs/ADR-004-consolidated-output-root.md](docs/architecture/adrs/ADR-004-consolidated-output-root.md) | Accepted (2026-05-27) |
| ADR 004 tdd workflow enforcement | [docs/architecture/adrs/ADR-004-tdd-workflow-enforcement.md](docs/architecture/adrs/ADR-004-tdd-workflow-enforcement.md) | Accepted (2026-05-27) |
| ADR 005 frontend coder agent | [docs/architecture/adrs/ADR-005-frontend-coder-agent.md](docs/architecture/adrs/ADR-005-frontend-coder-agent.md) | ADR-005: frontend-coder as a First-Class Sibling Implementation Agent |
| ADR 006 flatten supervisor chain | [docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md](docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md) | ADR-006: Flatten the Supervisor Chain — ticket-supervisor at Depth 0 |
| ADR 007 ac store schema id format enforcement | [docs/architecture/adrs/ADR-007-ac-store-schema-id-format-enforcement.md](docs/architecture/adrs/ADR-007-ac-store-schema-id-format-enforcement.md) | ADR-007: AC Store — YAML Schema, ID Format, and Bidirectional Enforcement Model |
| ADR 007 contract driven acs | [docs/architecture/adrs/ADR-007-contract-driven-acs.md](docs/architecture/adrs/ADR-007-contract-driven-acs.md) | ADR-007: Contract-Driven Acceptance Criteria |
| ADR 007 test fixture convention | [docs/architecture/adrs/ADR-007-test-fixture-convention.md](docs/architecture/adrs/ADR-007-test-fixture-convention.md) | Test Fixture Convention: load_fixture() Helper and tests/fixtures/ Directory Layout |
| ADR 009 itpo no source code access | [docs/architecture/adrs/ADR-009-itpo-no-source-code-access.md](docs/architecture/adrs/ADR-009-itpo-no-source-code-access.md) | ADR-009: IT Product Owner v3 — Source Code Access Restriction |
| ADR 010 ac store as authoritative backlog | [docs/architecture/adrs/ADR-010-ac-store-as-authoritative-backlog.md](docs/architecture/adrs/ADR-010-ac-store-as-authoritative-backlog.md) | ADR-010: AC Store as Authoritative Backlog — Source-of-Truth Inversion |

## How-To Guides

| Name | Path | Description |
|------|------|-------------|
| ac driven development | [docs/how-to/ac-driven-development.md](docs/how-to/ac-driven-development.md) | How to use the AC-driven development system |
| ac traceability store | [docs/how-to/ac-traceability-store.md](docs/how-to/ac-traceability-store.md) | How to use the AC Traceability Store |
| configure workflow allowlist | [docs/how-to/configure-workflow-allowlist.md](docs/how-to/configure-workflow-allowlist.md) | How to configure the workflow shell-command allowlist |
| creating a claude code hook | [docs/how-to/creating-a-claude-code-hook.md](docs/how-to/creating-a-claude-code-hook.md) | How to create a Claude Code hook |
| creating a skill | [docs/how-to/creating-a-skill.md](docs/how-to/creating-a-skill.md) | How to create a skill |
| creating an agent template | [docs/how-to/creating-an-agent-template.md](docs/how-to/creating-an-agent-template.md) | How to create an agent template |
| deprecating or removing artifacts | [docs/how-to/deprecating-or-removing-artifacts.md](docs/how-to/deprecating-or-removing-artifacts.md) | How to deprecate or remove an artifact |
| drain backlog with build backlog | [docs/how-to/drain-backlog-with-build-backlog.md](docs/how-to/drain-backlog-with-build-backlog.md) | How to drain the backlog automatically with /build-backlog |
| drive epic manually | [docs/how-to/drive-epic-manually.md](docs/how-to/drive-epic-manually.md) | How to drive an epic manually when epic-supervisor is unavailable |
| finalize feature | [docs/how-to/finalize-feature.md](docs/how-to/finalize-feature.md) | How to use /finalize-feature |
| inject project knowledge into agents | [docs/how-to/inject-project-knowledge-into-agents.md](docs/how-to/inject-project-knowledge-into-agents.md) | How to inject project knowledge into a portable agent |
| known failing tests baseline | [docs/how-to/known-failing-tests-baseline.md](docs/how-to/known-failing-tests-baseline.md) | How to Use the Known-Failing Tests Baseline |
| managing pre commit hooks | [docs/how-to/managing-pre-commit-hooks.md](docs/how-to/managing-pre-commit-hooks.md) | How to manage pre-commit hooks in leafcutter |
| adopt consolidated output root | [docs/how-to/output-layout/adopt-consolidated-output-root.md](docs/how-to/output-layout/adopt-consolidated-output-root.md) | How to adopt the consolidated output root (.leafcutter/) |
| working with leafcutter | [docs/how-to/working-with-leafcutter.md](docs/how-to/working-with-leafcutter.md) | How to work with leafcutter end-to-end |
| writing a tdd ticket | [docs/how-to/writing-a-tdd-ticket.md](docs/how-to/writing-a-tdd-ticket.md) | This guide walks you through writing a ticket that will go through the leafcutter |

## Reference

| Name | Path | Description |
|------|------|-------------|
| ac schema | [docs/reference/ac-schema.md](docs/reference/ac-schema.md) | Reference: AC Traceability Store Schema |
| agent teams constraints | [docs/reference/agent-teams-constraints.md](docs/reference/agent-teams-constraints.md) | Reference: Claude Code Agent Teams Constraints |
| agent template frontmatter | [docs/reference/agent-template-frontmatter.md](docs/reference/agent-template-frontmatter.md) | Reference: Agent Template Frontmatter Fields |
| claude code hooks | [docs/reference/claude-code-hooks.md](docs/reference/claude-code-hooks.md) | Reference: Claude Code Hooks |
| feedback concurrency | [docs/reference/feedback-concurrency.md](docs/reference/feedback-concurrency.md) | Reference: Feedback Client Concurrency Limitation |
| skill frontmatter | [docs/reference/skill-frontmatter.md](docs/reference/skill-frontmatter.md) | Reference: SKILL.md Frontmatter Fields |
| skills config fields | [docs/reference/skills-config-fields.md](docs/reference/skills-config-fields.md) | Reference: skills_config.json Fields |
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
| EPIC ACTraceabilityStore | [docs/retrospectives/EPIC-ACTraceabilityStore.md](docs/retrospectives/EPIC-ACTraceabilityStore.md) | Date: 2026-06-04 |
| EPIC CompletionManifestSignoff | [docs/retrospectives/EPIC-CompletionManifestSignoff.md](docs/retrospectives/EPIC-CompletionManifestSignoff.md) | Date: 2026-05-30 |
| EPIC ErrorHandlingEnforcement | [docs/retrospectives/EPIC-ErrorHandlingEnforcement.md](docs/retrospectives/EPIC-ErrorHandlingEnforcement.md) | Date: 2026-06-01 |
| EPIC FlattenSupervisorChain | [docs/retrospectives/EPIC-FlattenSupervisorChain.md](docs/retrospectives/EPIC-FlattenSupervisorChain.md) | Date: 2026-05-29 |
| EPIC FrontendAgent | [docs/retrospectives/EPIC-FrontendAgent.md](docs/retrospectives/EPIC-FrontendAgent.md) | Date: 2026-05-28 |
| EPIC MoveOnMainOnly | [docs/retrospectives/EPIC-MoveOnMainOnly.md](docs/retrospectives/EPIC-MoveOnMainOnly.md) | Date: 2026-06-03 |
| EPIC TDDWorkflowEnforcement | [docs/retrospectives/EPIC-TDDWorkflowEnforcement.md](docs/retrospectives/EPIC-TDDWorkflowEnforcement.md) | **Date**: 2026-05-27 |
| TICKET 20260601 FixHooksDeploymentPipeline | [docs/retrospectives/TICKET-20260601-FixHooksDeploymentPipeline.md](docs/retrospectives/TICKET-20260601-FixHooksDeploymentPipeline.md) | Date: 2026-06-01 |

## Glossary

- [docs/glossary.md](docs/glossary.md) — This file is auto-maintained by the glossary-automation system.

---
*Index generated by `scripts/generate_doc_index.py`.*
