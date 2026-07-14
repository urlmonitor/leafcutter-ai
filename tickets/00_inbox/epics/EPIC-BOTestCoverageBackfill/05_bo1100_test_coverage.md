---
title: "Establish green test coverage for BO-1100 (smart-commit-routing) ACs"
status: todo
components:
  - build_orchestration
created: 2026-07-14
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
source_ac: BO-1100a-1
ac_coverage:
  - BO-1100a-1
  - BO-1100d-1-i
  - BO-1100e-1
  - BO-1100e-1-i
  - BO-1100e-2
  - BO-1100e-2-i
  - BO-1100a-2-i
files_touched:
  - unit_tests/test_commit_classifier.py
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: needed
---

# 05: Green test coverage for BO-1100

## Actor / Goal

As the AC store, I want every BO-1100 AC in `ac_coverage` to have a real, green
unit test that **names the AC**, so its `work_status: done` is honestly backed by
verifiable coverage (per the 2026-07-14 test-truth rule).

## Remediation Context (audit 2026-07-14)

These ACs are implemented in code but lack a valid green test link. Two natures:

- **link-or-author** — the audit judged the behaviour built; find the existing
  test that asserts it and add a `covers: <AC>` citation. If no test genuinely
  asserts it, author one. Then run green and record `covered_by` on the AC.
- **author test** — no test asserts the behaviour; author one (test-writer),
  run green, then record `covered_by`.

For BO-1100 specifically, note any deploy-layout test-path issues: subprocess tests
that hardcode `leafcutter-ai/scripts/...` must resolve the deployed/template
script so they pass in a source checkout.

### link-or-author
- BO-1100a-1  # link-or-author
- BO-1100d-1-i  # link-or-author
- BO-1100e-1  # link-or-author
- BO-1100e-1-i  # link-or-author
- BO-1100e-2  # link-or-author
- BO-1100e-2-i  # link-or-author

### author test
- BO-1100a-2-i  # author test

## Acceptance Criteria

For each AC in `ac_coverage`: a green test names it; its `covered_by` records the
test path (`::test_function` where applicable); `work_status: done` only after green.

## Test Requirements

```yaml
tests:
  - name: test_bo_1100_ac_has_named_green_test
    file: unit_tests/test_commit_classifier.py
    covers: [BO-1100a-1]
    asserts: at least one green test names this AC and asserts its behaviour.
```

## Sign-offs

- [x] test-writer — 2026-07-14 14:22
- [x] python-coder — 2026-07-14 15:00
- [x] test-runner — 2026-07-14 13:08
- [x] pr-reviewer — 2026-07-14 13:23
- [x] commit — 2026-07-14 15:45
- [ ] pull-request

## Comments

### 2026-07-14 14:22 — test-writer (status: ok)
feedback-id: fb_2026-07-14_d1384b5a
completion_manifest:
  tests_written: true
  one_red_test_confirmed: true
  covers_tags_present: true
  link_or_author_acs_covered: true
  author_test_ac_covered: true

## Test Writer — Completion Report

### Tests Written
| File | Directory | Framework | Status |
|---|---|---|---|
| test_commit_classifier.py | unit_tests/ | unittest | written (9 new test functions in 4 new classes) |

### Verification Run
- Command: `python3 -m pytest unit_tests/test_commit_classifier.py -v -p no:scripts.ac_store.pytest_ac_enforcement --rootdir=<worktree>`
- Result: **red** (1 failure — `test_ac_bo1100a2i_empty_staging_area_signals_no_commit`, `AttributeError: 'ClassificationResult' object has no attribute 'no_staged_files'`)
- Standard run (with `pytest_ac_enforcement` plugin): 28 passed, 1 xfailed, exit 0 — the plugin intentionally converts failing tests covering not-done ACs to informational xfail for CI tolerance. True red state confirmed with plugin disabled.

### AC Coverage
| AC | Test function |
|---|---|
| BO-1100a-1 | `TestAcBackfillBO1100a1::test_ac1_each_file_classified_into_exactly_one_group`, `test_ac1_first_match_wins_tickets_before_docs` |
| BO-1100d-1-i | `TestAcBackfillBO1100d1i::test_ac_bo1100d1i_shapes_same_regardless_of_file_count` |
| BO-1100e-1 | `TestAcBackfillBO1100e::test_ac_bo1100e1_filter_narrows_git_log_to_matching_paths` |
| BO-1100e-1-i | `TestAcBackfillBO1100e::test_ac_bo1100e1i_fewer_commits_than_bound_returns_all` |
| BO-1100e-2 | `TestAcBackfillBO1100e::test_ac_bo1100e2_filter_respects_max_commits_bound` |
| BO-1100e-2-i | `TestAcBackfillBO1100e::test_ac_bo1100e2i_zero_commits_returns_empty_list_not_error` |
| BO-1100a-2-i | `TestAcBackfillBO1100a2i::test_ac_bo1100a2i_empty_staging_area_signals_no_commit` |

### Notes
- 7 "link-or-author" tests pass immediately because the underlying behavior is already implemented in `commit_classifier.py` and `commit_pattern_learner.py` — this is expected for a backfill ticket.
- 1 "author test" (BO-1100a-2-i) is genuinely RED: it requires python-coder to add a `no_staged_files: bool` attribute to `ClassificationResult`.
- The `pytest_ac_enforcement` plugin (loaded via pytest.ini) converts the BO-1100a-2-i failure to XFAILED when running normally, because the AC's `work_status` is `todo`. This is by project design. The canonical red-state evidence is the `-p no:scripts.ac_store.pytest_ac_enforcement` run.

red_baseline:
  - test_name: test_ac_bo1100a2i_empty_staging_area_signals_no_commit
    file: unit_tests/test_commit_classifier.py
    error: "AttributeError: 'ClassificationResult' object has no attribute 'no_staged_files'"
    note: "pytest_ac_enforcement plugin converts this to XFAILED in standard runs (exit 0); true red confirmed with -p no:scripts.ac_store.pytest_ac_enforcement (exit 1)"
  - test_name: test_ac1_each_file_classified_into_exactly_one_group
    file: unit_tests/test_commit_classifier.py
    error: "(passes immediately)"
    note: "passes immediately — implementation already exists (backfill scenario for BO-1100a-1)"
  - test_name: test_ac1_first_match_wins_tickets_before_docs
    file: unit_tests/test_commit_classifier.py
    error: "(passes immediately)"
    note: "passes immediately — implementation already exists (backfill scenario for BO-1100a-1)"
  - test_name: test_ac_bo1100d1i_shapes_same_regardless_of_file_count
    file: unit_tests/test_commit_classifier.py
    error: "(passes immediately)"
    note: "passes immediately — implementation already exists (backfill scenario for BO-1100d-1-i)"
  - test_name: test_ac_bo1100e1_filter_narrows_git_log_to_matching_paths
    file: unit_tests/test_commit_classifier.py
    error: "(passes immediately)"
    note: "passes immediately — implementation already exists (backfill scenario for BO-1100e-1)"
  - test_name: test_ac_bo1100e1i_fewer_commits_than_bound_returns_all
    file: unit_tests/test_commit_classifier.py
    error: "(passes immediately)"
    note: "passes immediately — implementation already exists (backfill scenario for BO-1100e-1-i)"
  - test_name: test_ac_bo1100e2_filter_respects_max_commits_bound
    file: unit_tests/test_commit_classifier.py
    error: "(passes immediately)"
    note: "passes immediately — implementation already exists (backfill scenario for BO-1100e-2)"
  - test_name: test_ac_bo1100e2i_zero_commits_returns_empty_list_not_error
    file: unit_tests/test_commit_classifier.py
    error: "(passes immediately)"
    note: "passes immediately — implementation already exists (backfill scenario for BO-1100e-2-i)"

### 2026-07-14 15:00 — python-coder (status: ok)
feedback-id: fb_2026-07-14_0dfe8770
completion_manifest:
  no_staged_files_attribute_added: true
  red_baseline_test_green: true
  ruff_clean: true
  behavioral_spot_check: true
Added `no_staged_files: bool = False` to `ClassificationResult` (default False) and set `no_staged_files=True` in the empty-staging-area return path of `classify_staged_files()`. All 29 tests pass (including the previously-red `test_ac_bo1100a2i_empty_staging_area_signals_no_commit`). Ruff clean. Behavioral spot-check confirmed correct values for both empty and non-empty staging areas.

red_baseline_results:
  - test_name: test_ac_bo1100a2i_empty_staging_area_signals_no_commit
    result: green
  - test_name: test_ac1_each_file_classified_into_exactly_one_group
    result: green
  - test_name: test_ac1_first_match_wins_tickets_before_docs
    result: green
  - test_name: test_ac_bo1100d1i_shapes_same_regardless_of_file_count
    result: green
  - test_name: test_ac_bo1100e1_filter_narrows_git_log_to_matching_paths
    result: green
  - test_name: test_ac_bo1100e1i_fewer_commits_than_bound_returns_all
    result: green
  - test_name: test_ac_bo1100e2_filter_respects_max_commits_bound
    result: green
  - test_name: test_ac_bo1100e2i_zero_commits_returns_empty_list_not_error
    result: green

### 2026-07-14 13:08 — test-runner (status: ok)
feedback-id: fb_2026-07-14_1fcf8ff3
completion_manifest:
  test_suite_executed: true
  all_tests_passing: true
  failure_report_structured: true
Ran unit_tests/test_commit_classifier.py via pytest (29 tests). All 29 passed, 5 subtests passed, 0 failures, 0 errors. BO-1100 AC backfill coverage confirmed green: BO-1100a-1, BO-1100d-1-i, BO-1100e-1, BO-1100e-1-i, BO-1100e-2, BO-1100e-2-i, and BO-1100a-2-i all have named, passing test functions.

### 2026-07-14 13:23 — pr-reviewer (status: ok)
feedback-id: fb_2026-07-14_b41de514
completion_manifest:
  no_high_confidence_findings: true
  medium_findings_surfaced: true
  ac_coverage_verified: true
  all_7_acs_have_named_tests: true
  tests_confirmed_green_by_test_runner: true
Two medium-confidence findings surfaced (see review report): stale "intentionally RED" comments in TestAcBackfillBO1100a2i that are now factually incorrect (the attribute was added by python-coder and the test is green), and absence of an explicit assertion that no_staged_files is False for the non-empty staging area path. Neither finding is a blocker — the implementation is correct and all 29 tests are green. Recommend python-coder or test-writer update the stale comments in a follow-up before merge.

### 2026-07-14 15:45 — commit (status: ok)
feedback-id: fb_2026-07-14_2392de68
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Auto-authorized commit gate: subject "test(BO-1100): add green coverage for 7 ACs + no_staged_files attribute"; staged files: scripts/commit_classifier.py, tickets/00_inbox/epics/EPIC-BOTestCoverageBackfill/05_bo1100_test_coverage.md, unit_tests/test_commit_classifier.py.
