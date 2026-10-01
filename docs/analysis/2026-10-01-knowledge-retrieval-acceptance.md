---
title: 'Knowledge retrieval acceptance fulfillment'
description: 'Verified KM-400 implementation outcomes and explicit deployment validation limits.'
type: explanation
status: active
created: '2026-10-01'
last_updated: '2026-10-01'
components:
  - knowledge_management
  - decision_kernel
---
# KM-400 acceptance fulfillment review

Review date: 2026-10-01. IT PO technical review follows PO/BA behavioral authoring, independent A/B/C source review and executed tests. `done` below means the bounded implementation described by the approved criteria is implemented and locally verified; it does not certify production rollout, external merge execution, new production memory schemas or real-model semantic quality. No verdict is inferred merely from a test tag.

| AC | Verdict and concrete evidence |
|---|---|
| a-1 | Done: Stage0 and ADR062 map canonical fields, IDs, directions, path targets/anchors and excluded surfaces; immutable source projection tests verify the mapping boundary. |
| a-2 | Done: exact service lookup and real Neo4j scope/idempotence tests preserve ID/revision/locator; absent IDs are empty success without semantic substitution. |
| a-3 | Done: all9 registered graph-template demonstrations plus live anchor/neighbor test verify directions, deterministic results and supported applicability; unmapped production policy/history kinds return unsupported. |
| a-4 | Done: contract unknown-version/operation/mode/argument validation rejects before retrieval; typed CLI error tests verify nonzero structured failures. Model-bound numeric limits reject invalid ranges. |
| a-5 | Done: foreign candidate, poisoned relationship source, response SHA/request binding, authenticated cursor and real vector-index scope tests reject cross-repository/generation data. |
| b-1 | Done: immutable Git preview ignores dirty files; repeated generation identity/counts and standalone real publication are tested without kernel startup. |
| b-2 | Done: duplicate IDs, missing required references, invalid schema and interrupted/invalid live publication preserve the active generation; optional references remain diagnostics. |
| b-3 | Done: real concurrent CAS, interrupted resumable construction, parented-history stale/non-descendant rejection and retained-generation reads prove complete publication and non-regression. |
| b-4 | Done: canonical rename/delete source fixture plus live generation replacement verify stable IDs, changed paths and removal of deleted content/relationships. |
| b-5 | Done: live rebuild equivalence, repository-isolated rollback/cleanup and retirement-time retention tests cover recoverability; expired continuation behavior is explicit. |
| c-1 | Done for explicitly reviewed synthetic extension: invalid/unreviewed memory rejected; synthetic correction/lesson/evidence records and outputs are labeled throughout. No production Decision/Lesson persistence schema is claimed. |
| c-2 | Done: model/hash/dimension-bound embedding job, HTTP fixture and real vector search verify bounded ranking and isolation; no similarity-derived canonical edge or correctness probability is generated. |
| c-3 | Done: real hybrid correction/lesson/evidence demonstration plus saturated-seed regression prove expansion remains available under candidate caps, and source paths/seed/ranking signals survive kernel mapping. |
| c-4 | Done: missing/mismatched vectors fail explicitly, model/content cache isolation and immutable ready-generation tests prevent stale-vector use; fallback policy is explicitly none and exact/graph remains available. |
| c-5 | Done for measurement and honesty: seven reviewed synthetic cases and all9 graph recipes record exact expected results, relevance/correction/provenance metrics and context/latency metadata. `semantic_usefulness_proven=false`; real-model evaluation is explicitly not run. |
| d-1 | Done: discovery serialization, structural-neighbor, approved summary/source and registered progressive tests enforce increasing disclosure without hidden source bodies. |
| d-2 | Done: immutable SHA source, exact YAML-pointer/line locator, traversal rejection and long UTF8 excerpts preserve attributable source and explicit missing/truncated limitations. |
| d-3 | Done: authenticated request-bound cursor tests cover changed scope/disclosure, retained SHA, page progression without skipped dropped rows and expiration. |
| d-4 | Done: serialized-envelope byte/token/candidate tests plus kernel cumulative follow-up and actual slow-port cancellation prove bounded output and partial/truncated reporting. |
| d-5 | Done: stable canonical evidence identity across separate retrieval runs is tested; exact stale revision behavior remains explicit and retained generations remain accessible. |
| e-1 | Done: fresh-process import/disabled CLI and kernel bootstrap tests prove optional startup; enabled missing configuration/dependency errors are typed and do not print secret values. |
| e-2 | Done: exact/sufficient helpers and actual ambiguous registered invocation prove deterministic bypass and exactly one budgeted existing Jev call; diagnostics record reason, no-fallback policy and disclosure budget. |
| e-3 | Done: actual KernelService graph completes a grounded decision with fake retrieval/Jev/host/human; reopening SQLite checkpoint retains canonical evidence, SHA, retrieval provenance and registered invocation. Scoped response, progressive depth, useful-budget-stop, outage and deadline tests exercise boundaries. |
| e-4 | Done: completed no-match, unavailable backend, stale generation and semantic-readiness tests distinguish failures; tracer-outage test preserves useful response and records loss. Existing research/kernel regressions retain escalation policy. |
| e-5 | Done locally: canonical-main secret-gated workflow static proof, real parented Git sync and requested/published SHA lag test cover replay/publication wiring; runbook supplies setup/off/rebuild/rollback/recovery. Actual GitHub merge execution is not run because this feature has not been merged. |

## Verification scope

C broad explicit-options run: `AC_ENFORCE_STRICT=1 python -m pytest tests/knowledge/test_integration.py tests/knowledge/test_kernel_bridge.py tests/knowledge/test_kernel_run.py tests/knowledge/test_workflow.py tests/kernel/config tests/kernel/contracts tests/kernel/registry tests/kernel/retrieval tests/kernel/capabilities tests/kernel/adapters/test_bootstrap.py -q --tb=short -o addopts= -p no:cacheprovider` produced **381 passed,144 subtests passed**,15.86s; one existing LangChain beta warning. Subsequent focused bridge/run tests after telemetry and stable-ID coverage plus diagnostic fields: **14 passed**,3.94s. Normal Ruff passes C-owned production/tests. All31 KM-400 YAML files validate using the canonical AC schema validator.

A reports54 combined new non-live tests at its last handoff; B reports12 live test functions (11 backend +1 catalog) on Neo4j5.26.31/driver6.0.3. Counts overlap C tests; do not add them. Durable live output artifacts: `reports/knowledge-retrieval-real-subset-status.json`, `reports/knowledge-retrieval-synthetic-evaluation.json`. See [detailed verification](2026-10-01-knowledge-retrieval-verification.md) for commands, red-first evidence and the per-function inventory.

## Explicit verification limits

- Full legacy AC corpus is rejected for three pre-existing required-reference errors: ACS-200d -> ACS-200b; ACS-600e -> ACS-600b; ACS-600e -> ACS-300f. The real ADR/component-only demonstration uses a separate identity and cannot replace the full projection.
- Production Decision/Lesson/Policy mappings remain unsupported. Synthetic memory is a reviewed demonstration, not historical production evidence.
- No paid embedding provider or real-model usefulness evaluation ran. Text above32KiB requires an explicit chunking adapter; automatic chunking is not implemented or advertised.
- External main-branch GitHub workflow execution, production credentials/permissions and other Neo4j versions are not tested. No push or merge is included in these verdicts.

Root independent final combined check: all11 new non-live files including full kernel_run passed **60 tests in11.23s** with explicit pytest options. Combined normal Ruff for knowledge, integrations, changed kernel modules and all new/live tests passed. B final component-hub provenance correction is verified separately after this combined run.

Pytest clarification: the recorded commands use `-o addopts=`. This omits the repository AC-enforcement plugin normally injected through addopts, so setting AC_ENFORCE_STRICT alone did not enable that plugin. These are direct, unmasked pytest assertion results; they are not proof that the default repository plugin workflow ran. Canonical AC schema validation was executed separately.

Subsequent user-authorized source repair update: the three historical missing dependencies above describe the original base revision only. BA has now amended the two source ACs, fixed four malformed GE1074 pytest selectors and verified all4490 canonical AC references/schema with no new cycles. Mapper3 full mutable preflight passes5989 nodes/19363 edges. Immutable full Aura publication remains a separate pending gate; see the [Aura acceptance extension](2026-10-01-knowledge-retrieval-aura-acceptance.md).
