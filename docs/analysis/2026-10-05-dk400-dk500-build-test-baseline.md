---
title: "Test Baseline Before the DK-400 and DK-500 Builds"
description: "The 13 tests failing on main at 28b6168c before the DK-400 (split compound requests) and DK-500 (reusable decision criteria) epics are built, by node id, with cause and owner. Recorded as Step 0 of decision dec-9925ebf1895222f4."
type: reference
status: active
created: 2026-10-05
last_updated: 2026-10-05
components:
  - decision_kernel
  - testing_quality
related_docs:
  - docs/decisions/dec-9925ebf1895222f4.yaml
  - docs/architecture/adrs/ADR-067-kernel-splits-bundled-requests-into-approved-parts.md
---

# Test baseline before the DK-400 and DK-500 builds

## Why this exists

Decision dec-9925ebf1895222f4 builds the two approved AC trees in seven epics:

- **DK-400**, split compound requests: 3 epics.
- **DK-500**, reusable decision criteria: 4 epics.

Its Step 0 requires main's failing tests to be recorded by node id before the first epic starts. A failing test in a file a planned ticket extends must be fixed or ticketed first. A fully green main is not required.

This record lets every epic's finalize-feature run tell regressions from pre-existing failures. It also lets a reviewer check that no epic made the list longer.

## Baseline

- **Main:** `28b6168cdd43d62d31248ff8283b69028b290814` (PR #1014).
- **CI run:** 37357952636. Test suite shards 1, 2, 3, 4, 6 and 7 of 8 fail. "Agent evals (affected)" fails on every PR, because the claude CLI cannot run in CI. That check is not a test failure.

| # | Test file | Test | Cause | Owner |
|---|---|---|---|---|
| 1 | `tests/kernel/capabilities/test_host_operations.py` | `TestCompiler::test_every_host_capability_of_the_design_has_an_operation` | `host.retrieval_needs` is in `OPERATIONS` but not in `SCHEMAS`. DK-400c-1 extends this file with `host.decompose_goal`. | ticket "host-operation test tables include host.retrieval_needs" (2026-10-05, this PR; blocks DK-400 E1) |
| 2 | `tests/kernel/grounding/test_retrieval_live_misses.py` | `TestRealRepositoryMisses::test_the_design_folder_is_fully_considered_and_the_record_part_is_found` | Live retrieval over the real repository | not yet ticketed |
| 3 | `tests/knowledge/test_kernel_run.py` | `TestKnowledgeRun::test_full_run_persists_attributable_knowledge_evidence` | Run ends `blocked` | not yet ticketed |
| 4 | `tests/knowledge/test_native_changelog_entry.py` | `test_changelog_real_corpus_accounts_for_all_fields_and_three_recoveries` | Real-store count | not yet ticketed |
| 5 | `tests/knowledge/test_native_decision_corpus.py` | `test_native_decision_real_corpus_preserves_all_authored_records` | Count pin of 6 (now 9 records) | ticket "knowledge real-corpus tests derive expected counts" (2026-10-05, PR #995) |
| 6 | `tests/knowledge/test_native_flow.py` | `test_flow_real_corpus_deep_equality_and_no_rewrites` | Count pin of 25 (now 27 flows) | ticket "knowledge real-corpus tests derive expected counts" (2026-10-05, PR #995) |
| 7 | `tests/knowledge/test_native_mock_data.py` | `test_mock_data_real_corpus_preserves_all_records_and_unregistered_dataset` | Count pin of 3 (now 4 datasets) | ticket "knowledge real-corpus tests derive expected counts" (2026-10-05, PR #995) |
| 8 | `tests/knowledge/test_native_mockup.py` | `test_mockup_real_canonical_population_includes_unregistered_and_null_renders` | Count pin of 15 (now 17 mockups) | ticket "knowledge real-corpus tests derive expected counts" (2026-10-05, PR #995) |
| 9 | `tests/knowledge/test_native_ticket.py` | `test_ticket_real_store_preserves_every_frontmatter_field` | Real-store fields | not yet ticketed |
| 10 | `tests/knowledge/test_query_answer_contract_acceptance_kernel.py` | `TestPublicKernelAnswerContract::test_foreign_evidence_diagnosis_compares_actual_scope_and_withholds_evidence` | Query-answer contract | not yet ticketed |
| 11 | `tests/knowledge/test_query_answer_contract_acceptance_kernel.py` | `TestPublicKernelAnswerContract::test_missing_fact_diagnosis_does_not_invent_remote_trace_or_root_cause` | Query-answer contract | not yet ticketed |
| 12 | `tests/knowledge/test_query_answer_contract_acceptance_kernel.py` | `TestPublicKernelAnswerContract::test_research_obligations_reach_actual_retrieval_and_persist` | Query-answer contract | not yet ticketed |
| 13 | `tests/knowledge/test_query_answer_contract_acceptance_kernel.py` | `TestPublicKernelAnswerContract::test_scripted_sufficient_judgment_cannot_upgrade_unresolved_answer` | Query-answer contract | not yet ticketed |

Rows 5 to 8 grow by one each time a decision record, flow, dataset or mockup is added. Until their ticket is built, an epic that adds such a record changes the asserted number, not the list of failing tests.

## How the builds use it

- The red-baseline gate checks only tests tagged `# covers: <ac-id>`. Pre-existing failures do not block a ticket.
- finalize-feature records its own baseline on main before each epic merges, and sorts pre-existing failures from regressions. Any failure not in this list counts as a regression of that epic.
- Row 1 sits in the file that DK-400c-1 extends, so its ticket is built before the DK-400 E1 epic starts.
