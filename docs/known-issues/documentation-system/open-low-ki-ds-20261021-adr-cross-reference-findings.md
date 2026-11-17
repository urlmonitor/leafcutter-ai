---
title: "KI-DS-20261021-adr-cross-reference-findings — 155 findings from the working check-adr-cross-reference: 43 ADR component links have no detail_ref, 56 detail_ref docs do not mention their ADR"
description: "low — GE-113c-5 made check-adr-cross-reference read the real project root; before, it found no registry, no ADR folder and no staged file. A strict sweep on 2026-10-21 over all 68 ADRs and the 30 components.json detail_ref docs reports 155 findings. Pre-commit runs the hook without --strict, so they surface as warnings, not refusals. This record names every one so whoever next edits an ADR or detail doc fixes its back-link in the same change."
type: reference
category: reference
status: active
created: '2026-10-21'
last_updated: '2026-10-21'
components:
  - documentation_system
  - commit_guardian
related_docs:
  - docs/known-issues/documentation-system.md
  - docs/known-issues/README.md
  - docs/known-issues/documentation-system/open-low-ki-ds-20261021-architecture-docs-with-broken-parent-links.md
---

# KI-DS-20261021-adr-cross-reference-findings — 155 findings from the repaired ADR cross-reference check

> Filed 2026-10-21 during EPIC-RightJobRightAgentFollowUps (GE-113c-5). Index: [documentation-system.md](../documentation-system.md).

- **Severity:** low. Nothing is broken at run time. `.pre-commit-config.yaml` runs
  `check_adr_cross_reference.py` **without `--strict`**, so these surface as warnings on a commit
  that stages an ADR or a `detail_ref` doc, and do not refuse it. Under `--strict` they would be errors.
- **Status:** open. Fix each ADR/doc pair when either is next edited, or in a dedicated back-link backfill.
- **Occurrences:** 1 · **First seen:** 2026-10-21 · **Last seen:** 2026-10-21

## Sweep

Run on 2026-10-21 with the repaired hook's own logic: `_collect_findings(<all 68 ADRs under
docs/architecture/adrs/>, <the 30 distinct detail_ref docs in docs/components.json>, components,
_build_adr_index(), strict=True)`. Result: **155 findings** = 43 (no `detail_ref`) + 56 (no back-link)
+ 56 (removed mention, the doc-side view of the same 56 pairs). Distinct root causes: 43 + 56 = 99.
Paths are under `docs/architecture/adrs/` for ADRs; doc paths are repo-relative.

**Kind A — no `detail_ref` (43):** the component the ADR lists has no `detail_ref` in `docs/components.json`, so the back-link cannot be verified. Components: `ac_store` (11), `supervisor_system` (7), `precommit_hooks` (6), `infrastructure` (5), `ticket_creation_pipeline` (3), `documentation_system` (3), `skills_system` (2), `testing_quality` (2), `config_loader` (1), `frontend_coding` (1), `review_system` (1), `git_vcs_operations` (1).

- `ADR-004-consolidated-output-root.md` — `infrastructure`
- `ADR-010-ac-store-as-authoritative-backlog.md` — `ac_store`, `ticket_creation_pipeline`
- `ADR-012-retire-create-ticket-js.md` — `ticket_creation_pipeline`, `ac_store`
- `ADR-013-portable-skill-script-deployment-boundary.md` — `skills_system`, `ac_store`
- `ADR-014-exception-guard-enforcement-scope.md` — `precommit_hooks`
- `ADR-015-guard-honors-noqa-ble001.md` — `precommit_hooks`
- `ADR-017-computed-quality-gates.md` — `supervisor_system`, `ticket_creation_pipeline`
- `ADR-020-live-surface-tester.md` — `config_loader`
- `ADR-021-plan-feature-product-truth-phase.md` — `ac_store`
- `ADR-023-product-truth-flow-first-upstream-layer.md` — `ac_store`
- `ADR-025-first-class-flow-decisions.md` — `frontend_coding`
- `ADR-026-ac-driven-build-v2-phased-migration.md` — `ac_store`
- `ADR-029-adr-number-collision-prevention.md` — `documentation_system`
- `ADR-030-dual-engine-workflow-support.md` — `supervisor_system`
- `ADR-031-worktree-quality-gate-guard.md` — `precommit_hooks`
- `ADR-032-tiered-parallel-code-smell-review.md` — `review_system`, `skills_system`, `supervisor_system`
- `ADR-034-knowledge-write-ownership.md` — `infrastructure`
- `ADR-035-fast-lane-closed-producer-roster.md` — `ac_store`
- `ADR-036-documentation-dispatch-caller-boundary.md` — `documentation_system`, `supervisor_system`, `ac_store`
- `ADR-037-whole-collection-uniqueness-pass.md` — `documentation_system`, `ac_store`
- `ADR-038-commit-guardian-shared-change-set-derivation.md` — `git_vcs_operations`
- `ADR-040-knowledge-write-publication-rides-completion-commit.md` — `infrastructure`
- `ADR-041-recomputed-attribution-at-item-granularity.md` — `infrastructure`
- `ADR-042-product-truth-checker-outcome-vocabulary.md` — `precommit_hooks`
- `ADR-043-journey-record-carries-its-own-behind-mark.md` — `precommit_hooks`
- `ADR-044-example-content-self-declares-its-product.md` — `ac_store`
- `ADR-046-completion-demanded-set-is-record-only.md` — `supervisor_system`
- `ADR-047-single-writer-ticket-close-path.md` — `supervisor_system`
- `ADR-048-order-independent-per-ticket-completion.md` — `supervisor_system`
- `ADR-049-record-checker-trigger-scope.md` — `precommit_hooks`
- `ADR-064-persona-discovery-before-feature-planning.md` — `ac_store`
- `ADR-069-durable-log-root-for-workspaces.md` — `infrastructure`
- `ADR-071-test-intent-is-not-a-test-contract.md` — `testing_quality`
- `ADR-072-code-aware-test-designer-may-read-source.md` — `testing_quality`

**Kind B — no back-link in the `detail_ref` doc (56):** the doc exists but does not mention the ADR by its file stem. Fix: add the stem to the doc's `related_docs` or body.

- `ADR-002-dual-platform-compilation.md` — `docs/build-pipeline.md` (component `build_pipeline`)
- `ADR-004-consolidated-output-root.md` — `docs/build-pipeline.md` (component `build_pipeline`)
- `ADR-005-frontend-coder-agent.md` — `docs/build-pipeline.md` (component `build_pipeline`)
- `ADR-006-flatten-supervisor-chain.md` — `docs/build-pipeline.md` (component `build_pipeline`)
- `ADR-007-contract-driven-acs.md` — `docs/build-pipeline.md` (component `build_pipeline`)
- `ADR-008-ac-store-schema-id-format-enforcement.md` — `docs/build-pipeline.md` (component `build_pipeline`)
- `ADR-009-itpo-no-source-code-access.md` — `docs/build-pipeline.md` (component `build_pipeline`)
- `ADR-010-ac-store-as-authoritative-backlog.md` — `docs/build-pipeline.md` (component `build_pipeline`)
- `ADR-011-learning-emission-sink.md` — `docs/build-pipeline.md` (component `build_pipeline`)
- `ADR-012-retire-create-ticket-js.md` — `docs/build-pipeline.md` (component `build_pipeline`)
- `ADR-013-portable-skill-script-deployment-boundary.md` — `docs/build-pipeline.md` (component `build_pipeline`)
- `ADR-014-exception-guard-enforcement-scope.md` — `docs/architecture/components/commit-guardian.md` (component `commit_guardian`)
- `ADR-015-guard-honors-noqa-ble001.md` — `docs/architecture/components/commit-guardian.md` (component `commit_guardian`)
- `ADR-016-ci-fresh-clone-test-dependencies.md` — `docs/build-pipeline.md` (component `build_pipeline`)
- `ADR-017-computed-quality-gates.md` — `docs/architecture/components/agent-registry.md` (component `agent_registry`)
- `ADR-018-agent-isolation-topology.md` — `docs/architecture/components/worktree-manager.md` (component `worktree_manager`), `docs/build-pipeline.md` (component `build_pipeline`), `docs/architecture/components/commit-guardian.md` (component `commit_guardian`)
- `ADR-019-build-feature-inline-phase-dispatch.md` — `docs/build-pipeline.md` (component `build_pipeline`)
- `ADR-020-live-surface-tester.md` — `docs/build-pipeline.md` (component `build_pipeline`)
- `ADR-021-plan-feature-product-truth-phase.md` — `docs/architecture/components/ux-prototyping.md` (component `ux_prototyping`), `docs/build-pipeline.md` (component `build_pipeline`)
- `ADR-022-mockups-are-the-real-app-in-mock-mode.md` — `docs/architecture/components/ux-prototyping.md` (component `ux_prototyping`), `docs/build-pipeline.md` (component `build_pipeline`)
- `ADR-023-product-truth-flow-first-upstream-layer.md` — `docs/build-pipeline.md` (component `build_pipeline`)
- `ADR-025-first-class-flow-decisions.md` — `docs/architecture/components/ux-prototyping.md` (component `ux_prototyping`), `docs/build-pipeline.md` (component `build_pipeline`)
- `ADR-026-ac-driven-build-v2-phased-migration.md` — `docs/build-pipeline.md` (component `build_pipeline`)
- `ADR-027-tdd-workflow-enforcement.md` — `docs/build-pipeline.md` (component `build_pipeline`)
- `ADR-028-test-fixture-convention.md` — `docs/build-pipeline.md` (component `build_pipeline`)
- `ADR-031-worktree-quality-gate-guard.md` — `docs/architecture/components/worktree-manager.md` (component `worktree_manager`), `docs/build-pipeline.md` (component `build_pipeline`), `docs/architecture/components/commit-guardian.md` (component `commit_guardian`)
- `ADR-032-tiered-parallel-code-smell-review.md` — `docs/architecture/components/agent-registry.md` (component `agent_registry`)
- `ADR-033-agent-model-tiers.md` — `docs/architecture/components/agent-registry.md` (component `agent_registry`), `docs/build-pipeline.md` (component `build_pipeline`)
- `ADR-034-knowledge-write-ownership.md` — `docs/architecture/components/knowledge-system.md` (component `knowledge_system`)
- `ADR-035-fast-lane-closed-producer-roster.md` — `docs/architecture/components/build-orchestration.md` (component `build_orchestration`), `docs/architecture/components/agent-registry.md` (component `agent_registry`)
- `ADR-036-documentation-dispatch-caller-boundary.md` — `docs/architecture/components/agent-registry.md` (component `agent_registry`)
- `ADR-037-whole-collection-uniqueness-pass.md` — `docs/architecture/components/ticket-lifecycle.md` (component `ticket_lifecycle`)
- `ADR-039-fast-lane-occupied-workspace-refusal.md` — `docs/architecture/components/worktree-manager.md` (component `worktree_manager`)
- `ADR-040-knowledge-write-publication-rides-completion-commit.md` — `docs/architecture/components/knowledge-system.md` (component `knowledge_system`), `docs/build-pipeline.md` (component `build_pipeline`), `docs/architecture/components/finalize.md` (component `finalize`)
- `ADR-041-recomputed-attribution-at-item-granularity.md` — `docs/build-pipeline.md` (component `build_pipeline`)
- `ADR-042-product-truth-checker-outcome-vocabulary.md` — `docs/architecture/components/ux-prototyping.md` (component `ux_prototyping`)
- `ADR-044-example-content-self-declares-its-product.md` — `docs/architecture/components/ux-prototyping.md` (component `ux_prototyping`)
- `ADR-050-runtime-reachability-guard-refuses-not-warns.md` — `docs/architecture/components/commit-guardian.md` (component `commit_guardian`), `docs/build-pipeline.md` (component `build_pipeline`)
- `ADR-062-standalone-knowledge-retrieval.md` — `docs/architecture/components/decision-kernel.md` (component `decision_kernel`)
- `ADR-064-persona-discovery-before-feature-planning.md` — `docs/architecture/components/knowledge-management.md` (component `knowledge_management`)
- `ADR-068-drift-exempt-gets-its-own-result-column.md` — `docs/build-pipeline.md` (component `build_pipeline`)
- `ADR-069-durable-log-root-for-workspaces.md` — `docs/build-pipeline.md` (component `build_pipeline`), `docs/architecture/components/knowledge-system.md` (component `knowledge_system`)
- `ADR-072-code-aware-test-designer-may-read-source.md` — `docs/architecture/components/agent-registry.md` (component `agent_registry`)

**Kind C — "removed mention" (56):** the reverse pass over the `detail_ref` docs. The same 56 ADR/doc pairs as Kind B, reported again from the doc side (the pass runs over every `detail_ref` doc), so fixing Kind B clears Kind C. Grouped by ADR:

- `ADR-002-dual-platform-compilation` — `docs/build-pipeline.md`
- `ADR-004-consolidated-output-root` — `docs/build-pipeline.md`
- `ADR-005-frontend-coder-agent` — `docs/build-pipeline.md`
- `ADR-006-flatten-supervisor-chain` — `docs/build-pipeline.md`
- `ADR-007-contract-driven-acs` — `docs/build-pipeline.md`
- `ADR-008-ac-store-schema-id-format-enforcement` — `docs/build-pipeline.md`
- `ADR-009-itpo-no-source-code-access` — `docs/build-pipeline.md`
- `ADR-010-ac-store-as-authoritative-backlog` — `docs/build-pipeline.md`
- `ADR-011-learning-emission-sink` — `docs/build-pipeline.md`
- `ADR-012-retire-create-ticket-js` — `docs/build-pipeline.md`
- `ADR-013-portable-skill-script-deployment-boundary` — `docs/build-pipeline.md`
- `ADR-014-exception-guard-enforcement-scope` — `docs/architecture/components/commit-guardian.md`
- `ADR-015-guard-honors-noqa-ble001` — `docs/architecture/components/commit-guardian.md`
- `ADR-016-ci-fresh-clone-test-dependencies` — `docs/build-pipeline.md`
- `ADR-017-computed-quality-gates` — `docs/architecture/components/agent-registry.md`
- `ADR-018-agent-isolation-topology` — `docs/architecture/components/commit-guardian.md`, `docs/architecture/components/worktree-manager.md`, `docs/build-pipeline.md`
- `ADR-019-build-feature-inline-phase-dispatch` — `docs/build-pipeline.md`
- `ADR-020-live-surface-tester` — `docs/build-pipeline.md`
- `ADR-021-plan-feature-product-truth-phase` — `docs/architecture/components/ux-prototyping.md`, `docs/build-pipeline.md`
- `ADR-022-mockups-are-the-real-app-in-mock-mode` — `docs/architecture/components/ux-prototyping.md`, `docs/build-pipeline.md`
- `ADR-023-product-truth-flow-first-upstream-layer` — `docs/build-pipeline.md`
- `ADR-025-first-class-flow-decisions` — `docs/architecture/components/ux-prototyping.md`, `docs/build-pipeline.md`
- `ADR-026-ac-driven-build-v2-phased-migration` — `docs/build-pipeline.md`
- `ADR-027-tdd-workflow-enforcement` — `docs/build-pipeline.md`
- `ADR-028-test-fixture-convention` — `docs/build-pipeline.md`
- `ADR-031-worktree-quality-gate-guard` — `docs/architecture/components/commit-guardian.md`, `docs/architecture/components/worktree-manager.md`, `docs/build-pipeline.md`
- `ADR-032-tiered-parallel-code-smell-review` — `docs/architecture/components/agent-registry.md`
- `ADR-033-agent-model-tiers` — `docs/architecture/components/agent-registry.md`, `docs/build-pipeline.md`
- `ADR-034-knowledge-write-ownership` — `docs/architecture/components/knowledge-system.md`
- `ADR-035-fast-lane-closed-producer-roster` — `docs/architecture/components/agent-registry.md`, `docs/architecture/components/build-orchestration.md`
- `ADR-036-documentation-dispatch-caller-boundary` — `docs/architecture/components/agent-registry.md`
- `ADR-037-whole-collection-uniqueness-pass` — `docs/architecture/components/ticket-lifecycle.md`
- `ADR-039-fast-lane-occupied-workspace-refusal` — `docs/architecture/components/worktree-manager.md`
- `ADR-040-knowledge-write-publication-rides-completion-commit` — `docs/architecture/components/finalize.md`, `docs/architecture/components/knowledge-system.md`, `docs/build-pipeline.md`
- `ADR-041-recomputed-attribution-at-item-granularity` — `docs/build-pipeline.md`
- `ADR-042-product-truth-checker-outcome-vocabulary` — `docs/architecture/components/ux-prototyping.md`
- `ADR-044-example-content-self-declares-its-product` — `docs/architecture/components/ux-prototyping.md`
- `ADR-050-runtime-reachability-guard-refuses-not-warns` — `docs/architecture/components/commit-guardian.md`, `docs/build-pipeline.md`
- `ADR-062-standalone-knowledge-retrieval` — `docs/architecture/components/decision-kernel.md`
- `ADR-064-persona-discovery-before-feature-planning` — `docs/architecture/components/knowledge-management.md`
- `ADR-068-drift-exempt-gets-its-own-result-column` — `docs/build-pipeline.md`
- `ADR-069-durable-log-root-for-workspaces` — `docs/architecture/components/knowledge-system.md`, `docs/build-pipeline.md`
- `ADR-072-code-aware-test-designer-may-read-source` — `docs/architecture/components/agent-registry.md`

## Fix direction

- Kind A: add a `detail_ref` to `docs/components.json` for the named component (or confirm it
  deliberately has none and exempt it in the hook through a recorded decision, not silently).
- Kind B/C: add the ADR file stem to the `detail_ref` doc's `related_docs` or body. One edit clears both kinds.
- Re-run the sweep with `--strict` to confirm. Flipping the hook to `--strict` in pre-commit waits until this backfill closes.
