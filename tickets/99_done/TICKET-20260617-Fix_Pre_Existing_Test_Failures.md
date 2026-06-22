---
title: "Fix 24 pre-existing unit-test failures (tree_traversal, transform_hooks, visualise_knowledge_graph)"
status: done
components:
  - testing_quality
  - ac_store
  - commit_guardian
  - knowledge_system
created: 2026-06-17
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
tags:
  - test-debt
  - pre-existing
roadmap_phase: phase_1
advances_current_outcome: true
---

# Fix 24 Pre-Existing Unit-Test Failures

## Actor / Goal

In order to keep the test suite green and trustworthy as a regression gate, we
need to fix the 24 unit-test failures that already exist on `origin/main`, so
that future epic finalize drives are not forced to triage a standing baseline of
red tests as "pre-existing" on every run.

## Context

Discovered during the `EPIC-BuildGuardFalsePositive` finalize drive on 2026-06-17.
The `test-failure-triage` agent classified all 24 failures as `pre_existing`
(`blocks_finalization: false`) — they were present on `origin/main` **before** the
epic merge and are **not** caused by it. PR #97 merged cleanly on that basis. This
ticket tracks fixing them so the baseline returns to green.

The 24 failures fall into three independent clusters, each with a distinct root
cause. They could reasonably be split into three sibling tickets (or an epic) if
the work warrants; each cluster ships and is useful alone.

> **Caveat — re-verify before fixing.** These failures were observed both via the
> finalize triage (on the post-merge `origin/main` worktree) and on a stale local
> `main` checkout. Cluster 2 (`FileNotFoundError` on missing scripts) in particular
> should be **re-confirmed against a fresh `origin/main` checkout** before
> implementation, in case any part is a stale-tree artifact rather than a genuine
> gap. Run the three test files on a clean `git pull`'d `main` first.

## Acceptance Criteria

```gherkin
Scenario: Cluster 1 — ac_store leaf traversal returns only leaves (AC-1)
  Given unit_tests/ac_store/test_tree_traversal.py
  When the full file is run against origin/main
  Then all 5 previously-failing tests pass
  And traverse_ac_tree() returns only leaf ACs (no intermediate nodes with covered_by children)

Scenario: Cluster 2 — commit_guardian transform hooks importable (AC-2)
  Given unit_tests/commit_guardian/test_transform_hooks_and_autofix_emission.py
  When the full file is run against a fresh origin/main checkout
  Then all 12 previously-failing tests pass
  And the scripts they import resolve (no FileNotFoundError on transform_doc_frontmatter.py / transform_description_field.py)

Scenario: Cluster 3 — visualise_knowledge_graph emits valid HTML (AC-3)
  Given unit_tests/test_visualise_knowledge_graph.py
  When the full file is run against origin/main
  Then all 7 previously-failing tests pass
  And scripts/visualise_knowledge_graph.py no longer raises ValueError at the graph-build step

Scenario: full suite returns to green baseline (AC-4)
  Given the full unit-test suite on origin/main after this ticket
  When pytest runs
  Then these 24 specific failures no longer appear in the failure set
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |

## Failure Inventory

### Cluster 1 — `unit_tests/ac_store/test_tree_traversal.py` (5 failures)

Root cause: `traverse_ac_tree()` returns intermediate (non-leaf) nodes in addition
to leaves. Example: expected `{'ACD-050a-1-i','ACD-050a-2','ACD-050b-1'}` but got
`['ACD-050a-1','ACD-050a-1-i','ACD-050a-2','ACD-050b-1']` — the intermediate node
`ACD-050a-1` (which has `covered_by` children) is incorrectly included. The
leaf-detection predicate appears wrong.

- `TestTraverseAcTreeLeafCollection::test_ac1_leaf_only_returned_from_mixed_tree`
- `TestTraverseAcTreeLeafCollection::test_ac1_depth_first_alphabetical_order`
- `TestTraverseAcTreeLeafCollection::test_ac1_performance_200_nodes`
- `TestTraverseAcTreeLeafCollection::test_ac1_absent_covered_by_treated_as_leaf`
- `TestTraverseAcTreeL1Scope::test_ac1i_leaf_l1_returns_itself`

### Cluster 2 — `unit_tests/commit_guardian/test_transform_hooks_and_autofix_emission.py` (12 failures)

Root cause: `FileNotFoundError` importing
`scripts/commit_guardian/transform_doc_frontmatter.py` and
`scripts/commit_guardian/transform_description_field.py` — these script files
referenced by the tests do not exist at the expected path. Either the scripts were
never created / were moved, or the test import paths are stale. **Re-verify against
fresh origin/main (see caveat above).**

- `TestTransformDocFrontmatterFillsMissingFields::test_transform_doc_frontmatter_fills_missing_fields`
- `TestTransformDocFrontmatterFillsMissingFields::test_transform_doc_frontmatter_preserves_existing_fields`
- `TestTransformDocFrontmatterFailOpen::test_transform_doc_frontmatter_fail_open`
- `TestTransformDocFrontmatterFailOpen::test_transform_doc_frontmatter_no_op_outside_docs_layout`
- `TestTransformDescriptionFieldStubsFromTitle::test_transform_description_field_no_op_when_present`
- `TestTransformDescriptionFieldStubsFromTitle::test_transform_description_field_stubs_from_title`
- `TestTransformDescriptionFieldFailOpen::test_transform_description_field_fail_open`
- `TestTransformDescriptionFieldFailOpen::test_transform_description_field_fail_open_malformed_yaml`
- `TestHooksManifestTierField::test_hooks_manifest_tier_field`
- `TestCheckExceptionHandlingEmitsAutofixAgent::test_check_exception_handling_emits_autofix_agent`
- `TestCheckExceptionHandlingNoEmissionClean::test_check_exception_handling_no_emission_clean`
- (one additional test in the same file)

### Cluster 3 — `unit_tests/test_visualise_knowledge_graph.py` (7 failures)

Root cause: `ValueError` raised at `scripts/visualise_knowledge_graph.py:265`.

- `TestWritesHtmlFile::test_writes_html_file`
- `TestEmbeddedJsonValid::test_embedded_json_valid`
- `TestNodesHaveColorField::test_nodes_have_color_field`
- `TestNodeStructure::test_embedded_nodes_have_required_fields`
- `TestEdgeStructure::test_embedded_edges_have_required_fields`
- `TestD3CdnReference::test_html_references_d3_cdn`
- `TestSurfaceFilterExcludesOthers::test_surface_filter_excludes_others`
- `TestProjectRootFlagPassedToKq::test_project_root_flag_passed_to_kq`

## Comments

### 2026-06-18 — finalize-feature (EPIC-Acpatternenforcementismechanically)

The EPIC-Acpatternenforcementismechanically finalize drive captured a fresh
pre-merge baseline at `origin/main` (`19002fd`) and found **34** failing tests —
the 24 inventoried above (Clusters 1–3) **plus 10 more in two clusters not yet
tracked here**. Post-merge run was identical (34 = baseline exactly, 0 regressions
from the epic). Adding the two new clusters so the tracker is complete:

#### Cluster 4 — `tests/commit_guardian/test_diagram_type_enum.py` (5 failures)
- `test_bogus_diagram_type_rejected`
- `test_canonical_diagram_type_accepted[agent_flow]`
- `test_canonical_diagram_type_accepted[data_flow]`
- `test_canonical_diagram_type_accepted[user_flow]`
- `test_legacy_alias_still_accepted`

#### Cluster 5 — `tests/commit_guardian/test_commit_guardian_imports.py` (4 failures) + `tests/test_install_hooks.py` (1)
- `test_diagram_type_validators_present_and_callable`
- `test_module_imports_cleanly[check_doc_frontmatter]`
- `test_module_imports_cleanly[check_secrets]`
- `test_module_imports_cleanly[frontmatter_validators]`
- `test_install_hooks.py::TestInstallHooksPrecommitFailureIsNonfatal::test_install_hooks_precommit_failure_is_nonfatal`

Clusters 4–5 likely share a root cause with Cluster 2 (missing/relocated
commit-guardian scripts + diagram-type validator wiring). The title count (24)
is now understated — the true standing baseline is **34**. Re-verify all five
clusters on a fresh `main` before fixing.

## Implementation Tasks

- [ ] Re-run the three test files against a freshly `git pull`'d `main` to confirm
      which failures are genuine (esp. Cluster 2 FileNotFound).
- [ ] Cluster 1: fix the leaf-detection predicate in `traverse_ac_tree()` so
      intermediate nodes are excluded; confirm all 5 tests green.
- [ ] Cluster 2: restore/relocate the missing `transform_doc_frontmatter.py` and
      `transform_description_field.py` scripts (or fix the test import paths if the
      scripts moved); confirm all 12 tests green.
- [ ] Cluster 3: fix the `ValueError` at `visualise_knowledge_graph.py:265`; confirm
      all 7 tests green.
- [ ] Run the full unit-test suite and confirm these 24 failures no longer appear.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Test-and-script fixes are additive/corrective; trivially revertible.
- Note: if Cluster 2 requires re-creating deleted scripts, confirm they are also
  wired into the build manifest so they deploy to consumers (relates to the
  BP-900 manifest-derivation work just completed in EPIC-BuildGuardFalsePositive).

## Resolution (2026-06-22)

Closed via PR #144 (squash `19b618c`). Re-verification against current `main`
found the documented baseline was **stale**: only **14** of the claimed 24–34
failures were genuine. Clusters 2, 4, and `commit_guardian_imports` (21 tests)
were already fixed on `main` — the stale-tree artifacts the caveat warned about.

All 14 genuine failures were **stale tests, not production bugs** — production
code is unchanged:

- **Cluster 1** (`test_tree_traversal.py`, 5): tests asserted the superseded
  covered_by-based leaf definition; production is level-based (`leaf == level in
  {L2,L3}`) across `scan_ac_store.py`, `build_ac_mode_detection.py`,
  `goal_to_epic.py`. `ACD-1200a-1` no longer exists. Rewrote to the level-based
  contract. New AC: ACS-1000.
- **Cluster 3** (`test_visualise_knowledge_graph.py`, 8): `_assemble_graph` now
  delegates to `knowledge_query._collect_all`, but the test mock stubbed only the
  old granular API → tuple-unpack ValueError. Rewrote the mock factory. New AC:
  KM-VIS-014.
- **Cluster 5** (`test_install_hooks.py`, 1): test never simulated a git repo, so
  BP-007's deliberate not-a-git-repo guard short-circuited it. Mocked the
  `rev-parse --git-dir` probe. Covers existing BP-007.

Out-of-scope follow-up: 6 additional pre-existing failures were discovered that
were never in this ticket's inventory (`test_epic_folder_assembly` ACD-1200a-3,
`test_scan_ac_store_cycle` ACD-1200c-3, `test_build_file_size_injection` ×2,
`test_goal_to_epic_worktree_skip` BP-901, `test_skill_registry` orphaned
`create-ac`). Several are unimplemented-feature tests. Tracked separately.
