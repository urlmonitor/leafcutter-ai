---
title: 'Knowledge retrieval verification evidence'
description: 'Verified KM-400 implementation outcomes and explicit deployment validation limits.'
type: explanation
status: active
created: '2026-10-01'
last_updated: '2026-10-01'
components:
  - knowledge_management
  - decision_kernel
---
# Knowledge retrieval implementation verification

Status: implementation and local acceptance review complete; final delivery/commit handoff is separate. All25 leaf verdicts are recorded in the acceptance review. Production rollout, external merge execution and real-model semantic quality are not claimed.

## Isolation and roles

All implementation is in `worktrees/knowledge-retrieval-v01`, branch `feature/knowledge-retrieval-v01`, based on kernel v0.1 commit `3299cc3c`. No merge or push is included. Implementation commit handoff is recorded separately by the orchestrator. The parent orchestrates only. PO, BA and IT PO authored/reviewed KM-400 (31 records, including 25 implementation leaves). Source/test lead owns the standalone contracts, service and first behavioral tests; B owns immutable projection and Neo4j; C owns the thin kernel integration and operations. B and C add RED tests before their corresponding later behavior.

Canonical source and compatibility decisions: [Stage 0](2026-10-01-knowledge-retrieval-stage0.md), [ADR-062](../architecture/adrs/ADR-062-standalone-knowledge-retrieval.md). Source audit completed before production mapping. Initial supported surfaces are ACs, ADRs, components and referenced path-keyed files/tests. Other surfaces are explicitly excluded because source-wide IDs collide; no ID reassignments or hidden precedence. Decision/Lesson demonstrations are synthetic fixtures, not production memory ingestion.

## Test-first evidence

Runtime: `C:/Users/Hendrik/Code/leafcutter/.venv/Scripts/python.exe`, Python 3.14.2, pytest 9.1.1, PyYAML 6.0.3, Pydantic 2.13.5. Tests import new modules inside test functions, so the first missing implementation runs as individual failures, not collection or syntax errors.

- `python -m pytest tests/knowledge/test_core.py -q --tb=short -o addopts=`: first 14 failures, then strengthened discovery/hybrid suite 16 failures; expected ModuleNotFoundError/CLI assertions before knowledge package existed. Initial implementation: 16 passed. Subsequent adversarial coverage: 20 passed (these additional checks were already green and are not claimed as new RED-first evidence).
- `python -m pytest tests/knowledge/test_projection.py tests/knowledge/test_integration.py -q --tb=line -o addopts=`: 8 failures before production (5 projection, 3 integration). Temporary Git fixtures executed; no syntax/collection errors.
- Core retained-revision, level-1 structure and cumulative byte pagination regression additions: 3 failed /20 passed. Failures were stale instead of retained SHA, missing related-neighbor structure, and actual 3346 serialized bytes exceeding a cumulative 3000 budget. Fix: 23 passed.
- `python -m pytest tests/knowledge/test_evaluation.py -q --tb=short -o addopts=`: 1 missing-module failure before evaluation implementation, then 1 passed.
- Latest A targeted command: `python -m pytest tests/knowledge/test_core.py tests/knowledge/test_evaluation.py -q --tb=short -o addopts=`: **24 passed**. This is not a claim that B/C or the full MVP is done.

Normal repository Ruff check of A code and initial tests passed. Formatting performed with repository Ruff configuration. Strict error-policy lint is still being cleaned and will be recorded separately.

## Backend matrix and live verification

B verified Docker-accessible Neo4j Community **5.26.31**, image family `neo4j:5.26-community`, driver **6.0.3** on Python 3.14.2. Image digest reported by B: `sha256:5eb12ad77fa46ab73e23df9ea1f43f5c0f2a79523435577648e046be042b9b93`. Initial five real-backend tests passed (B owns final commands/counts). Do not infer Aura, 2026.x or other server-version compatibility from this test.

## Evaluation semantics

`knowledge.evaluation.evaluate` measures precision/recall at returned k, correction coverage, provenance validity, response bytes and observed latency; records SHA, generation, query and embedding model versions. Reviewed cases must identify a reviewer. CLI: `python -m knowledge evaluate --backend neo4j --repository-id <id> --cases <file>`. Synthetic mechanics intentionally report `semantic_usefulness_proven: false`. A representative real-model corpus baseline and threshold approval remain separate, unclaimed work.

## Unrelated legacy test observations

An exploratory whole `tests/knowledge` run included legacy knowledge-emission tests: 149 passed /7 failed while C was still implementing. Four failures were the not-yet-written C adapter. Three existing Windows-sensitive failures were:

1. `test_harvest_learnings_inf400c4iv.py::TestASinkThatExistsButCannotBeReadKeepsItsDistinctNonzeroStatus::test_a_sink_that_exists_but_cannot_be_read_keeps_its_distinct_nonzero_status`: chmod-based unreadability does not enforce unreadable access in this Windows run; absent and readable-invalid fixture both returned zero.
2. `test_inf_400c_4.py::test_parity_check_blocks_when_the_two_sides_resolve_to_different_paths`: expected raw Windows path is compared to escaped repr in output.
3. `test_inf_400c_5_h1_deployed_layout.py::test_build_deploys_all_three_h1_knowledge_artefacts_and_emit_knowledge_runs`: copying the entire worktree encounters access-denied `pytest-of-Hendrik` temporary directory.

These have not been fixed or counted as new retrieval regressions. Final verification uses explicitly named new files and C's relevant kernel regression suite.

## Remaining external validation limits

- The full canonical AC corpus is correctly rejected for historical required references ACS-200d -> ACS-200b, ACS-600e -> ACS-600b and ACS-600e -> ACS-300f. Real ADR/component subset publication is separately scoped, not full-corpus proof.
- Production Decision/Lesson/Policy mappings are not approved. Synthetic fixtures demonstrate mechanics and measured deterministic behavior only.
- Real-model semantic usefulness and production deployment privileges remain untested; no paid provider call ran.
- The opt-in canonical-main workflow is locally checked, but actual GitHub execution is deferred until the user's later merge. No push or merge was performed.

Implementation validation is complete across standalone service, real Neo4j publication/concurrency/vector catalog, full kernel decision/checkpoint, schema, documentation and independent review. See the [acceptance review](2026-10-01-knowledge-retrieval-acceptance.md) for per-leaf verdicts and non-overlapping interpretation of test counts.

## Updated A verification and independent review

A final additional regressions: embedding ingestion job RED1 -> GREEN1; explicit local HTTP gateway RED1 -> GREEN1; CLI missing driver/backend failure RED2 -> GREEN2; long UTF-8 source RED1 -> GREEN1; independent C review hybrid saturation and foreign relationship source RED2 -> GREEN2. The semantic follow-up instrumentation passed when added and is not claimed as RED-first.

The request gateway configuration is frozen. Remote Neo4j and embedding transports require verified TLS; local loopback development endpoints are allowed. Disabled startup performs no connectivity checks. SDK-free embedding gateway protocol is explicitly `POST {model,texts}` -> `{model,vectors}`, not a vendor API assumption. Provider identity/model/dimensions/text-version/content-bound ingestion caching is separate from retrieval caching. Long approved embedding texts above32KiB are rejected with a chunk-adapter-required message; no unimplemented chunking or real-model evaluation is claimed.

Core normal Ruff and strict E722,BLE001,TRY checks passed before final module split; they will be rerun for final handoff. Independent B review found and requested eligible-only vector readiness, dimension/rebinding protection, source locator fidelity and missing-reference diagnostics. Independent C review found dropped structural provenance and serialized follow-up budget accounting; C added a failing behavioral conversion test and corrected both. C independently found hybrid seed saturation and foreign relationship-source metadata leakage; A captured two failing tests and fixed both.

`python -m pytest tests/knowledge/test_core.py tests/knowledge/test_evaluation.py tests/knowledge/test_embedding_jobs.py tests/knowledge/test_http_embeddings.py tests/knowledge/test_cli_failures.py tests/knowledge/test_projection.py tests/knowledge/test_source_boundaries.py tests/knowledge/test_integration.py tests/knowledge/test_kernel_bridge.py tests/knowledge/test_workflow.py -q --tb=short -o addopts= -p no:cacheprovider` passed49 tests before the last two A and one C review regressions were added. Final rerun recorded below when complete.

All25 tickets were generated from approved ACs. Their actual grouped test pointers and touched-file metadata now point to implementation artifacts; no leaf has been marked done solely from test-tag counts.

## Current tagged coverage inventory

This inventory includes both isolated non-live tests and explicit real-Neo4j checks. It is not an independent fulfillment verdict.

- KM-400a-1: `tests/knowledge/test_projection.py::test_projection_reads_commit_not_dirty_checkout_and_reuses_identity`; `tests/knowledge/test_source_boundaries.py::test_snapshot_rejects_unknown_types_and_unreviewed_memory`
- KM-400a-2: `tests/knowledge/test_core.py::test_discovery_preserves_identity_without_loading_source`; `tests/knowledge_live/neo4j_checks.py::test_live_idempotence_scope_metadata_and_rebuild`
- KM-400a-3: `tests/knowledge_live/catalog_checks.py::test_all_registered_templates_and_measured_synthetic_evaluation`; `tests/knowledge_live/neo4j_checks.py::test_live_graph_neighbors_preserve_edge_anchor_and_bound`
- KM-400a-4: `tests/knowledge/test_core.py::test_invalid_operation_and_conflicting_arguments_fail_closed`
- KM-400a-5: `tests/knowledge/test_core.py::test_foreign_backend_candidate_never_reaches_evidence`; `tests/knowledge/test_core.py::test_foreign_relationship_source_cannot_cross_disclosure_boundary`; `tests/knowledge/test_kernel_bridge.py::test_foreign_backend_evidence_is_rejected_at_kernel_seam`; `tests/knowledge/test_kernel_bridge.py::test_port_response_revision_must_match_published_result`; `tests/knowledge_live/neo4j_checks.py::test_live_idempotence_scope_metadata_and_rebuild`; `tests/knowledge_live/neo4j_vector_checks.py::test_live_vectors_validate_hash_dimension_model_and_isolate_index`
- KM-400b-1: `tests/knowledge/test_projection.py::test_projection_reads_commit_not_dirty_checkout_and_reuses_identity`; `tests/knowledge_live/neo4j_checks.py::test_live_idempotence_scope_metadata_and_rebuild`; `tests/knowledge_live/neo4j_checks.py::test_live_sync_parented_history_rejects_late_and_non_descendant`
- KM-400b-2: `tests/knowledge/test_projection.py::test_duplicate_canonical_id_rejects_snapshot`; `tests/knowledge/test_projection.py::test_required_missing_reference_rejects_before_loader_drops_edge`; `tests/knowledge/test_source_boundaries.py::test_valid_yaml_missing_criteria_is_rejected`; `tests/knowledge_live/neo4j_checks.py::test_live_invalid_build_cannot_replace_active`
- KM-400b-3: `tests/knowledge_live/neo4j_checks.py::test_live_cas_publication_deletion_and_pinned_generation`; `tests/knowledge_live/neo4j_checks.py::test_live_interrupted_build_is_invisible_and_resumable`; `tests/knowledge_live/neo4j_checks.py::test_live_invalid_build_cannot_replace_active`; `tests/knowledge_live/neo4j_checks.py::test_live_sync_parented_history_rejects_late_and_non_descendant`
- KM-400b-4: `tests/knowledge/test_projection.py::test_rename_keeps_id_and_deleted_entity_disappears`; `tests/knowledge_live/neo4j_checks.py::test_live_cas_publication_deletion_and_pinned_generation`
- KM-400b-5: `tests/knowledge_live/neo4j_checks.py::test_live_idempotence_scope_metadata_and_rebuild`; `tests/knowledge_live/neo4j_checks.py::test_live_retention_starts_when_generation_is_retired`
- KM-400c-1: `tests/knowledge/test_source_boundaries.py::test_snapshot_rejects_unknown_types_and_unreviewed_memory`; `tests/knowledge_live/catalog_checks.py::test_all_registered_templates_and_measured_synthetic_evaluation`
- KM-400c-2: `tests/knowledge/test_core.py::test_hybrid_expands_synthetic_corrected_decision_with_separate_signals`; `tests/knowledge/test_embedding_jobs.py::test_reviewed_decision_text_cache_is_model_and_content_bound`; `tests/knowledge/test_http_embeddings.py::test_configured_provider_executes_model_bound_embedding_over_http`; `tests/knowledge_live/neo4j_vector_checks.py::test_live_ann_kind_filter_cannot_hide_only_matching_decision`; `tests/knowledge_live/neo4j_vector_checks.py::test_live_vectors_validate_hash_dimension_model_and_isolate_index`
- KM-400c-3: `tests/knowledge/test_core.py::test_hybrid_expands_synthetic_corrected_decision_with_separate_signals`; `tests/knowledge/test_core.py::test_hybrid_reserves_graph_work_when_ann_fills_its_limit`; `tests/knowledge_live/neo4j_vector_checks.py::test_live_synthetic_hybrid_service_expands_correction_lesson_evidence`
- KM-400c-4: `tests/knowledge/test_core.py::test_semantic_unready_is_not_empty_success`; `tests/knowledge/test_core.py::test_vector_dimension_and_nonfinite_fail_closed_before_search`; `tests/knowledge/test_embedding_jobs.py::test_reviewed_decision_text_cache_is_model_and_content_bound`; `tests/knowledge_live/neo4j_vector_checks.py::test_live_vector_reservation_and_ready_generation_are_immutable`; `tests/knowledge_live/neo4j_vector_checks.py::test_live_vectors_validate_hash_dimension_model_and_isolate_index`
- KM-400c-5: `tests/knowledge/test_evaluation.py::test_reviewed_cases_measure_relevance_corrections_provenance_and_size`; `tests/knowledge_live/catalog_checks.py::test_all_registered_templates_and_measured_synthetic_evaluation`; `tests/knowledge_live/neo4j_vector_checks.py::test_live_synthetic_hybrid_service_expands_correction_lesson_evidence`
- KM-400d-1: `tests/knowledge/test_core.py::test_discovery_preserves_identity_without_loading_source`; `tests/knowledge/test_core.py::test_discovery_serialization_cannot_leak_summary_or_properties`; `tests/knowledge/test_core.py::test_level_one_exposes_bounded_structure_without_neighbor_body`; `tests/knowledge/test_kernel_bridge.py::test_registered_graph_request_progresses_from_discovery_to_selected_source`
- KM-400d-2: `tests/knowledge/test_core.py::test_long_utf8_source_retains_useful_labeled_excerpt_within_full_budget`; `tests/knowledge/test_core.py::test_pinned_old_sha_followup_uses_retained_generation`; `tests/knowledge/test_core.py::test_source_disclosure_uses_pinned_reference_and_preserves_whitespace`; `tests/knowledge/test_projection.py::test_git_source_resolver_uses_sha_and_blocks_traversal`; `tests/knowledge/test_source_boundaries.py::test_yaml_pointer_reads_exact_criterion_not_file_header`
- KM-400d-3: `tests/knowledge/test_core.py::test_cursor_cannot_change_scope_or_disclosure_and_session_stops`; `tests/knowledge/test_core.py::test_limit_reports_truncation_and_integrity_checked_continuation`; `tests/knowledge/test_core.py::test_small_budget_pagination_never_skips_dropped_rows`
- KM-400d-4: `tests/knowledge/test_core.py::test_cursor_cannot_change_scope_or_disclosure_and_session_stops`; `tests/knowledge/test_core.py::test_full_serialized_result_including_metadata_fits_byte_cap`; `tests/knowledge/test_core.py::test_limit_reports_truncation_and_integrity_checked_continuation`; `tests/knowledge/test_core.py::test_long_utf8_source_retains_useful_labeled_excerpt_within_full_budget`; `tests/knowledge/test_core.py::test_semantic_followup_uses_remaining_candidate_budget`; `tests/knowledge/test_kernel_bridge.py::test_small_caller_excerpt_cap_is_never_widened`; `tests/knowledge_live/neo4j_checks.py::test_live_graph_neighbors_preserve_edge_anchor_and_bound`
- KM-400d-5: `tests/knowledge/test_core.py::test_missing_exact_revision_is_stale_without_silent_fallback`
- KM-400e-1: `tests/knowledge/test_core.py::test_import_does_not_load_kernel_or_optional_sdks_in_fresh_process`; `tests/knowledge/test_core.py::test_no_match_is_distinct_from_disabled`; `tests/knowledge/test_http_embeddings.py::test_configured_provider_executes_model_bound_embedding_over_http`; `tests/knowledge/test_integration.py::test_disabled_cli_is_reachable_without_kernel_bootstrap`
- KM-400e-2: `tests/knowledge/test_integration.py::test_exact_mode_choice_skips_jev_and_evidence_mapping_preserves_sha`; `tests/knowledge/test_integration.py::test_sufficient_evidence_mode_choice_stops_retrieval`
- KM-400e-3: `tests/knowledge/test_integration.py::test_exact_mode_choice_skips_jev_and_evidence_mapping_preserves_sha`; `tests/knowledge/test_kernel_bridge.py::test_foreign_backend_evidence_is_rejected_at_kernel_seam`; `tests/knowledge/test_kernel_bridge.py::test_graph_conversion_preserves_relationship_and_correction_provenance`; `tests/knowledge/test_kernel_bridge.py::test_port_response_must_belong_to_this_request`; `tests/knowledge/test_kernel_bridge.py::test_registered_binding_consumes_scoped_fake_port`; `tests/knowledge/test_kernel_bridge.py::test_registered_graph_request_progresses_from_discovery_to_selected_source`
- KM-400e-4: `tests/knowledge/test_cli_failures.py::test_cli_reports_typed_nonzero_failure`; `tests/knowledge/test_core.py::test_deadline_and_backend_outage_are_not_negative_evidence`; `tests/knowledge/test_core.py::test_no_match_is_distinct_from_disabled`; `tests/knowledge/test_kernel_bridge.py::test_unavailable_backend_does_not_become_empty_success`
- KM-400e-5: `tests/knowledge/test_source_boundaries.py::test_status_reports_requested_and_published_revision_lag`; `tests/knowledge/test_workflow.py::test_merge_workflow_is_canonical_secret_gated_and_uses_standalone_sync`; `tests/knowledge_live/neo4j_checks.py::test_live_sync_parented_history_rejects_late_and_non_descendant`

## Final A handoff checks

- The combined ten-file non-live command above now passes **54 tests in6.37s** after independent review fixes, source-boundary additions, and module split. Cache provider disabled for this run; no warnings.
- A production modules pass normal repository Ruff plus explicit `--select E722,BLE001,TRY`.
- `python scripts/ac_store/validate_ac_schema.py docs/acceptance-criteria/knowledge-management/KM-400-trustworthy-project-knowledge`: **all31 YAML files valid** after actual covered_by pointers were reconciled.
- Standalone implementation is frozen after independent AC validation. B and C append their exact real-server/evaluation/kernel results below. No production database, external provider or Git merge was performed.


## Final C integration and acceptance handoff

C broad explicit-options regression passed381 tests and144 subtests in15.86s, with one existing LangChain beta warning. Command and clause-specific verdicts are recorded in [acceptance review](2026-10-01-knowledge-retrieval-acceptance.md). Subsequent focused bridge/full-run tests after final telemetry/stable-ID checks and explicit policy/budget diagnostics passed14 in3.94s. New test_kernel_run completes the actual KernelService decision through fake host/human with an injected port and reopens SQLite checkpoint to verify evidence SHA/retrieval references. Ambiguous registered invocation uses exactly one scripted Jev call and budget reservation. Ruff passes C modules/tests. No external provider or GitHub workflow ran.

Root independent final combined check: all11 new non-live files including full kernel_run passed **60 tests in11.23s** with explicit pytest options (repository addopts disabled to preserve genuine failure exit status). Combined normal Ruff for knowledge, integrations, changed kernel modules and all new/live tests passed. B final component-hub provenance correction is verified separately after this combined run.

## Final B projection and real-server handoff

Final strict run passed **22 tests in 10.39 seconds**: ten source/projection tests and twelve actual Neo4j tests. Command: `AC_ENFORCE_STRICT=1 python -m pytest tests/knowledge/test_projection.py tests/knowledge/test_source_boundaries.py tests/knowledge_live/neo4j_checks.py tests/knowledge_live/catalog_checks.py -q --tb=short -p no:cacheprovider -W ignore::DeprecationWarning`. Environment: Windows Python 3.14.2, neo4j driver 6.0.3 and local Neo4j Community 5.26.31. The pinned image and dependency are in `knowledge/compose.yaml` and `knowledge/requirements-neo4j.txt`. Final normal Ruff passed knowledge modules, live checks and source-boundary tests.

The final publication regression failed before its fix and passed afterward: a concurrent CAS loser remains validated and cannot be retrieved by generation or source revision. Only successful pointer publication atomically marks a generation ready. Rollback cannot expose an unpublished generation. The final run also verifies interrupted/resumed builds, idempotence, deletions, retained readers, retirement-based cleanup, ancestry rejection, vector reservation conflicts, immutable ready vectors, per-kind ANN indexes and model/dimension/hash validation.

`reports/knowledge-retrieval-synthetic-evaluation.json` records all nine supported graph recipes, seven deterministic evaluation cases, eight entities, eight relationships and three eligible embeddings. Precision/recall, correction coverage and provenance coverage are 1.0 for this explicitly synthetic corpus/provider; this is not real-model usefulness proof. `reports/knowledge-retrieval-real-subset-sync.json` and `reports/knowledge-retrieval-real-subset-status.json` record mapper-2 publication of 121 real ADR/component nodes and 147 edges at the base SHA in a separate repository scope. `reports/knowledge-retrieval-real-component-evidence.json` proves canonical registry-ID lookup and the exact JSON excerpt. Parent-linked Git fixture sync/status additionally exercises late/divergent revision refusal and explicit lag reporting.

B implementation and evidence are frozen. Production ownership: Git/source excerpt and Neo4j adapters, projection loader/validation, sync CLI, migration, pinned local setup and synthetic demonstration. Tests: `test_projection.py`, `test_source_boundaries.py` and `tests/knowledge_live/`. No hosted workflow, paid provider, push or merge ran. Three historical full-corpus reference errors and absent approved production memory mapping remain explicit limits.

## Local commit handoff limitation

The delegated commit agent inspected the existing shared hook without modifying it and attempted the documented worktree-only `ensure_precommit_config.py` bootstrap. Windows refused the runtime symlink with WinError 1314 (missing symlink privilege). The fallback copied a local configuration, but the guardian runtime remained undeployed. The required source probe `templates/scripts/commit_guardian/verify_precommit_active.py --json` exited 1: config, git hook, and canary passed; `incomplete_build` and `binary` failed. The root virtual environment contains the pre_commit 4.6.2 Python package but no discoverable pre-commit executable. No hook was bypassed, no shared runtime was modified, and no automatic approval rejection occurred.

The temporary copied configuration was removed after the failed probe. Feature changes remain uncommitted and unmerged on `feature/knowledge-retrieval-v01`, based on `3299cc3c`; nothing was staged. The unrelated untracked `pytest-of-Hendrik/` directory remains because its operating-system ACL refuses removal; it is not part of the intended delivery. No runtime copy, full deployment, package installation, push, or merge was attempted during commit preparation.
Final cleanup: the root orchestrator inspected the task-created `leafcutter-knowledge-test` container (`neo4j:5.26-community`), confirmed it used only two anonymous volumes and no host bind mounts, and successfully removed the container and its anonymous volumes after saving the evidence artifacts. Root's final `git diff --check` passed. No files are staged; the branch remains `feature/knowledge-retrieval-v01`, and the temporary `.pre-commit-config.yaml` is absent. This final record changes no implementation or tests and does not create a commit.
## Aura environment follow-up

User-provided Aura convention is now accepted by optional serving configuration, without kernel imports or credentials copied into Git. KM-400e-1/e-5 technical requirements and test coverage were amended. Test-first baseline: three failures and one pass for serving .env aliases/precedence/error naming; writer source compatibility separately failed before its change. Final targeted run: `python -m pytest tests/knowledge/test_environment.py tests/knowledge/test_cli_failures.py tests/knowledge/test_integration.py tests/knowledge/test_kernel_bridge.py -q -o addopts= -p no:cacheprovider` passed27 tests. Nine new environment tests cover Aura username/database, source and alias precedence, exact custom names, disabled no-read behavior, missing/unreadable files, empty-value fallback, and independent writer credentials. Only synthetic fixture values were used. Actual Aura connectivity is recorded separately by the read-only probe; these tests do not claim a successful cloud connection.

Final Aura compatibility regression: all12 new non-live test files passed **69 tests in9.11s** using explicit `-o addopts= -p no:cacheprovider`; this does not claim strict AC enforcement was loaded. The existing status test double now accepts the optional root argument; its behavior assertions are unchanged. Root independently ran the nine environment tests: **9 passed in0.30s** with the same explicit pytest options. Canonical schema validation passed all31 AC YAML files. Normal Ruff passed all changed Python files; the optional strict TRY check found only the two existing unrelated cli_sync ValueError-message rules, not introduced by this follow-up. No live Aura request or database write is claimed.

Aura database follow-up: two focused tests first failed because serving and writer used neo4j instead of the saved database. Both now honor NEO4J_DATABASE and LEAFCUTTER_NEO4J_DATABASE; explicit configured database wins, unset config is null, fallback remains neo4j, and NEO4J_INSTANCE remains metadata only. Kernel defaults/schema were regenerated. Environment plus kernel configuration checks:44passed and89subtests; all12 new non-live files:71passed9.90s; all31 AC YAMLs schema-valid; normal Ruff clean. B independently confirmed actual build_retriever construction selected the saved Aura database and a read-only RETURN1 managed transaction succeeded, then closed the driver. No Aura writes, staging or commits occurred.

Pytest clarification: the recorded commands use `-o addopts=`. This omits the repository AC-enforcement plugin normally injected through addopts, so setting AC_ENFORCE_STRICT alone did not enable that plugin. These are direct, unmasked pytest assertion results; they are not proof that the default repository plugin workflow ran. Canonical AC schema validation was executed separately.

## Deployment preparation after user continuation

Aura inventory read found0nodes,0relationships, no existing knowledge repository/generation, and2ONLINE LOOKUP indexes. Separate writer variables were absent. For this user-authorized deployment only, the supplied account will be explicitly bound to process-local writer credentials; this is same-principal administration, not evidence of least-privilege separation. The deployment plan is additive projection constraints/indexes plus immutable publication for repository_id leafcutter; no reset, unrelated deletion, cleanup or vector-memory fabrication is authorized.

The previous local commit blocker was resolved using the repository's narrow build phases for guardian, doc compliance, feedback, skills and precommit config, with copy shims confined to this worktree. An isolated .knowledge-hook-venv contains pre_commit4.6.2; generated outputs are excluded from delivery. The initial shared-hook refresh was rejected by automatic approval review because it affects all worktrees. The user then explicitly authorized the shared refresh. After checking no active commit/task-index lock, the original interpreter reinstalled the standard launcher; its bytes and configured interpreter remained identical to the backed-up original. The mandatory activation probe now reports binary/config/git_hook/canary all true and failing_checks empty. No hook was disabled or bypassed. Source commit/publication remains gated on repaired full-corpus projection validation.

Subsequent user-authorized source repair update: the three historical missing dependencies above describe the original base revision only. BA has now amended the two source ACs, fixed four malformed GE1074 pytest selectors and verified all4490 canonical AC references/schema with no new cycles. Mapper3 full mutable preflight passes5989 nodes/19363 edges. Immutable full Aura publication remains a separate pending gate; see the [Aura acceptance extension](2026-10-01-knowledge-retrieval-aura-acceptance.md).


## Actual proof-promise reconciliation

The actual hook exposed missing angle claims on existing public service/kernel tests plus two useful missing checks. Added standalone malformed-JSON CLI tests (four invalid-field cases, spy proves zero retrieval calls) and public service stable-evidence/distinct-run identity proof. Public service/catalog/registered-binding tests now explicitly claim the exercised reachability angle. Five source/projection lifecycle descriptors (a1,b1,b2,b4,b5) now promise real_artifact evidence matching their immutable Git/actual Neo4j tests; underlying AC behavior remains unchanged. Helper-only tests were not relabeled as public reachability. The full completed-kernel/checkpoint proof remains present even though the claim scanner does not pick up its async unittest method reliably; the synchronous registered-binding test also explicitly claims its actual criterion proof.

B final split verification:55 passed57.51s across source boundaries, canonical producer tests and the graph/vector/catalog live suites, including12 actual local Neo4j tests. The local test container and its disposable volumes were cleaned afterward. No Aura writes were part of those tests.
