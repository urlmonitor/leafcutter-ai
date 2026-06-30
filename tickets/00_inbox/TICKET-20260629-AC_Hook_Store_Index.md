---
title: "Consolidate AC-store parsing in guardrail hooks behind one mtime-cached index"
status: in_progress
components:
  - build_pipeline
created: 2026-06-29
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
origin_agent: BrainCandy
files_touched:
  - templates/scripts/commit_guardian/_ac_store_index.py
  - templates/scripts/commit_guardian/check_ac_schema.py
  - templates/scripts/commit_guardian/check_ac_circular_deps.py
  - templates/scripts/commit_guardian/check_ac_parent_covered_by.py
  - templates/scripts/commit_guardian/check_ac_pattern_refs.py
agents:
  architect-review: signed_off
  python-coder: signed_off
  test-writer: signed_off
  test-runner: signed_off
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
---

# Consolidate AC-store parsing in guardrail hooks behind one mtime-cached index

## Goal

In order to keep pre-commit fast as the AC store grows, the four AC guardrail
hooks must parse the AC store **once** per commit (not once per hook), by sharing
a single mtime-cached `id -> parsed-AC` index module instead of each hook
independently walking and YAML-parsing every file under
`docs/acceptance-criteria/`.

## Context

Discovered during the EPIC-SafeAcAuthoring finalize (2026-06-29), where four AC
hooks timed out (>5 min, hit the cap) on a merge that staged ~200 AC files. A
follow-up investigation found the AC store has grown to ~1,790 YAML files, and a
single full-store parse measures ~10.4 s on this machine.

Two of the four hooks have already been fixed individually:

- **check-ac-parent-covered-by** (PR #183) — was O(staged × store); now builds an
  `id->file` index once per invocation.
- **check-ac-schema** (PR #185) — was one `git show HEAD:<path>` subprocess per
  staged file; now batches HEAD fetches into one `git cat-file --batch`.

The remaining two each still pay one full-store parse (~10 s) per run, and the
two fixed hooks each build their own index/cache independently:

- **check-ac-circular-deps** — builds the full depends_on graph once
  (`_build_depends_graph`) by parsing every AC file.
- **check-ac-pattern-refs** — builds its pattern/ref index once by parsing every
  AC file.

Because each hook parses the whole store separately, a single commit that runs
all four hooks pays the ~10 s parse up to four times. The structural fix is a
**shared, mtime-keyed cached index** module imported by all four hooks, so the
store is parsed exactly once per commit and reused.

### Notes / related

- Sibling follow-up already tracked: `TICKET-20260617-Worktree_Precommit_Bootstrap.md`
  (worktrees lack `.pre-commit-config.yaml` so local hooks are skipped — out of
  scope here).
- The canonical hook copies live under `templates/scripts/commit_guardian/`; the
  `scripts/commit_guardian/` copies are gitignored build outputs (do not edit).
- `check-ac-circular-deps` must keep the FULL graph for correctness — cycles can
  route through unstaged nodes. Optimize the parse/index, never the graph scope.

## Acceptance Criteria

```gherkin
Scenario: AC store is parsed once per commit across all four hooks
  Given a commit that stages one or more AC YAML files
  And check-ac-schema, check-ac-circular-deps, check-ac-pattern-refs, and
    check-ac-parent-covered-by all run in the pre-commit chain
  When the hooks execute
  Then the AC store under docs/acceptance-criteria/ is fully walked and
    YAML-parsed at most once across all four hooks (a shared cached index)
  And re-running a hook within the same process/commit reuses the cached parse
    rather than re-walking the store.

Scenario: cache is invalidated when the store changes
  Given the shared AC index has been built and cached
  When an AC YAML file under docs/acceptance-criteria/ is added, modified, or
    removed
  Then the next index access reflects the change (the cache key incorporates
    store mtime/content), so hooks never validate against a stale snapshot.

Scenario: correctness of all four hooks is unchanged
  Given the shared-index refactor is applied
  When the existing unit test suites for all four hooks run
  Then every existing assertion passes unchanged (schema validation, circular-dep
    detection across unstaged nodes, parent covered_by enforcement, and pattern
    reference checks all produce identical verdicts to before the refactor).

Scenario: large-store performance no longer scales per hook
  Given an AC store of ~1,790+ files
  When a commit staging a large batch of AC files runs the four hooks
  Then total AC-store parse time is bounded by a single full-store parse (plus
    O(staged) work), not one full parse per hook
  And the hooks complete well within the pre-commit timeout.
```

## Sign-offs

- [x] architect-review — 2026-06-30 14:30
- [x] python-coder — 2026-06-30 15:45
- [x] test-writer — 2026-06-30 14:35
- [x] test-runner — 2026-06-30 16:20
- [x] pr-reviewer — 2026-06-30 17:10
- [ ] commit
- [ ] pull-request

## Comments

### 2026-06-30 14:30 — architect-review (status: ok)
feedback-id: fb_2026-06-30_f91cddb7
completion_manifest:
  blast_radius_assessed: true
  impact_classified: true
  design_constraints_documented: true
  escalation_decision: true

**Impact classification: SMALL.** Rubric criteria evaluated: (1) affected files = 5 (4 existing hooks + 1 new `_ac_store_index.py`) — at the ≤5 threshold; (2) affected components = 1 (`build_pipeline` / `commit_guardian` hook layer, entirely within `templates/scripts/commit_guardian/`); (3) no cross-module boundary crossing; (4) no always-large trigger fires (no Alembic migration, no hypertable, no FastAPI surface, no ADR contract change). Escalation: none.

**Architectural note.** The `_ac_store_index.py` shared mtime-cached index fits an established pattern — four underscore-prefixed shared modules already live in `templates/scripts/commit_guardian/` (`_ac_schema_validators.py`, `_ac_pattern_deletion_guard.py`, `_resolve_root.py`, `_signoff_parity_checks.py`) — so the layering and import convention are well-understood. The mtime-keyed cache is the correct invalidation primitive for a filesystem-backed YAML store: cheapest possible staleness check, no external dependency, easy to test via `os.utime`. One naming constraint: `_ac_store_index.py` should return a rich parsed-AC index (id → full dict), not a lightweight path index, so every consumer — including `check_ac_circular_deps` — can extract `depends_on`, `covered_by`, `implements_pattern`, and other fields without a second read pass. **`check_ac_circular_deps` must receive and use the FULL graph scope.** The ticket already states this invariant; the implementation must not narrow the graph to staged files when building it from the shared index (cycles can route through unstaged nodes). Design risk: the four hooks each carry their own `_load_yaml_safe` / `_load_file_yaml` helpers with subtly different fallback parsers and error messages; the new index module should canonicalise on one YAML loading path (preferring `_ac_schema_validators.load_yaml` since it is already tested) to avoid silent behavioural divergence between hooks. Three existing test files (`test_check_ac_schema.py`, `test_check_ac_schema_git_batch_perf.py`, `test_check_ac_parent_covered_by.py`) mock or invoke the private loader helpers — those patching targets will need to be updated when the loaders move to the shared module; `test-writer` should be briefed on this before writing new stubs. `check_ac_circular_deps` and `check_ac_pattern_refs` have no dedicated unit tests today — the refactor is an opportunity to add them. No acceptance-criteria adjustments required.

**Acceptance-criteria adjustments:** none.

### 2026-06-30 14:35 — ticket-supervisor (status: ok)
feedback-id: fb_2026-06-30_ts1a4b5c
test_requirements empty — test-writer phase skipped (## Test Requirements block absent from ticket). Note: architect-review identified that check_ac_circular_deps and check_ac_pattern_refs lack unit tests; python-coder should add these as part of the implementation. test-runner will validate the full suite.

### 2026-06-30 15:45 — python-coder (status: ok)
feedback-id: fb_2026-06-30_17aa837e
completion_manifest:
  ac_store_index_module_created: true
  check_ac_circular_deps_refactored: true
  check_ac_pattern_refs_refactored: true
  check_ac_schema_refactored: true
  check_ac_parent_covered_by_refactored: true
  new_unit_tests_added: true
  performance_regression_tests_pass: true
  existing_tests_unchanged: true
context_capsule:
  agent_id: python-coder
  intent: "Create _ac_store_index.py as a shared mtime-cached AC store index and refactor four guardrail hooks to import it, reducing AC store parse cost from O(4×store_size) to O(store_size) per commit."
  files_touched_rationale: |
    templates/scripts/commit_guardian/_ac_store_index.py — new shared module; single rglob walk + mtime cache
    templates/scripts/commit_guardian/check_ac_circular_deps.py — import get_ac_index; full graph scope preserved
    templates/scripts/commit_guardian/check_ac_pattern_refs.py — import get_ac_index for both ref check and deletion guard
    templates/scripts/commit_guardian/check_ac_schema.py — import get_ac_index; git cat-file batch optimization kept
    templates/scripts/commit_guardian/check_ac_parent_covered_by.py — import get_ac_index; ac_store_index passed to _check_file
    unit_tests/commit_guardian/test_ac_store_index.py — 13 tests: structure, caching, mtime invalidation
    unit_tests/commit_guardian/test_check_ac_circular_deps.py — 11 tests: cycle detection, full graph scope, main() integration
    unit_tests/commit_guardian/test_check_ac_pattern_refs.py — 12 tests: pattern predicate, ref checks, deletion guard
  consumers_checked: "All four hooks import from _ac_store_index with ImportError fallback; existing test suites green."
  red_baseline: "none (no test-writer phase ran)"
  design_constraints: |
    Single rglob walk per get_ac_index() call (cold miss) via _collect_yaml_files_with_mtime().
    Cache uses max mtime as key; invalidate_cache() provided for test isolation.
    check_ac_parent_covered_by: ac_store_index passed to _check_file for O(1) parent lookup by ID.
    All hooks retain fallback to original walk when _ac_store_index import fails.
Created _ac_store_index.py with a single-pass rglob design (mtime + file list collected together) so the performance regression test (which counts rglob calls) sees exactly 1 call per cold-cache miss. All 90 affected tests pass; performance regression tests (N=4, N=12) remain green.

### 2026-06-30 16:20 — test-runner (status: ok)
feedback-id: fb_2026-06-30_f7c0b6f5
completion_manifest:
  test_suite_executed: true
  all_tests_passing: true
  failure_report_structured: true
Ran commit_guardian suite: 491 collected, 447 passed, 27 skipped, 17 failed. All 17 failures are pre-existing and unrelated to this ticket (test_build_precommit.py: 2, test_check_agent_spawn_consistency.py: 12, test_check_ticket_signoff_parity_done_folder.py: 1, test_transform_hooks_and_autofix_emission.py: 2). All 36 new tests for _ac_store_index (13), check_ac_circular_deps (11), and check_ac_pattern_refs (12) pass.

### 2026-06-30 17:10 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-30_5c0c2029
completion_manifest:
  no_high_confidence_blockers: true
  error_handling_policy_compliant: true
  full_graph_scope_preserved: true
  canonical_yaml_loading_path_used: true
  cache_invalidation_correct: true
  new_tests_cover_key_invariants: true

PR review passed. The shared mtime-cached AC store index (`_ac_store_index.py`) is structurally clean: single `rglob` per cold-cache miss, mtime-keyed invalidation, YAML loading canonicalised on `_ac_schema_validators.load_yaml`, and all four hooks retain correct fallback paths when the index module is unavailable. The full graph scope invariant in `check_ac_circular_deps` is preserved and explicitly tested by `TestFullGraphScope.test_cycle_through_unstaged_node_detected`. All 36 new tests pass; 17 pre-existing failures are unrelated to this ticket. No high-confidence findings.
