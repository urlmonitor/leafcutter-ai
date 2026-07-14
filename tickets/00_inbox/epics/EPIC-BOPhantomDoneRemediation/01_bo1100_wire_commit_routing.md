---
title: "Wire commit agent to the classifier/learner library + config-array schema"
status: todo
components:
  - build_orchestration
created: 2026-07-14
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
source_ac: BO-1100a-2
ac_coverage:
  - BO-1100a-1-i
  - BO-1100a-2
  - BO-1100a-3
  - BO-1100a-4
  - BO-1100a-5
  - BO-1100b-1
  - BO-1100b-1-i
  - BO-1100b-2
  - BO-1100b-3
  - BO-1100b-3-i
  - BO-1100c-1
  - BO-1100c-1-i
  - BO-1100c-2
  - BO-1100c-3
  - BO-1100c-3-i
  - BO-1100d-2
  - BO-1100d-2-i
  - BO-1100d-3
  - BO-1100d-3-i
  - BO-1100d-4
  - BO-1100e-3
files_touched:
  - templates/agents/commit.md
  - config/commit_message_patterns.json
  - scripts/commit_classifier.py
  - scripts/commit_pattern_learner.py
  - unit_tests/test_commit_classifier.py
  - unit_tests/test_mixed_set_detection.py
agents:
  architect-review: signed_off
  test-writer: signed_off
  python-coder: failed
  sql-coder: not_needed
  test-runner: failed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 01: Wire commit agent to the classifier/learner library

## Actor / Goal

As the commit pipeline, I want the commit agent to actually invoke the existing
`commit_classifier` / `commit_pattern_learner` library so that the smart
commit-routing behaviour the BO-1100 ACs specify runs at commit time — instead
of the agent drafting messages free-hand while the tested library sits orphaned.

## Remediation Context (audit 2026-07-14)

**Phantom-done.** `scripts/commit_classifier.py` and
`scripts/commit_pattern_learner.py` are real and green (150 passing tests), but
`templates/agents/commit.md` Step 2 drafts messages free-hand and **never calls
them** — every `change_target: prompt` AC in BO-1100 is unwired. Two config
divergences also exist: `config/commit_message_patterns.json` is a
`group→template` **object** with path rules hard-coded in Python `_PATH_RULES`,
not the AC-specified **array of `{group, path_pattern, template}`** — so a routing
rule cannot be added via config.

**Do: wire, don't rewrite.** The library exists; the work is (a) invoke the
classifier + mixed-set detection + learner from `commit.md`, (b) convert the
config to the AC's array schema and read path rules from it, (c) surface
classification/mixed-commit warnings/rule proposals per the ACs. Preserve the
existing green tests; add tests that assert the agent actually invokes the library.

## Acceptance Criteria

Resolves the 21 leaf ACs listed in `ac_coverage` (see the AC store under
`docs/acceptance-criteria/build-orchestration/BO-1100-smart-commit-routing/` for
verbatim Gherkin). Definition of done: each cited AC's behaviour executes at
commit time and is asserted by a test that names the AC.

## Test Requirements

```yaml
tests:
  - name: test_commit_agent_invokes_classifier
    file: unit_tests/test_commit_classifier.py
    covers: [BO-1100a-2, BO-1100a-3, BO-1100a-4]
    asserts: The commit flow calls the classifier and routes by first-match group.
  - name: test_mixed_commit_warning_surfaced
    file: unit_tests/test_mixed_set_detection.py
    covers: [BO-1100b-1, BO-1100b-2, BO-1100b-3]
    asserts: A mixed change-set produces the enumerated warning and proceed/abort prompt.
  - name: test_routing_config_is_array_schema
    file: unit_tests/test_commit_patterns_config.py
    covers: [BO-1100c-1, BO-1100c-2]
    asserts: config is an array of {group, path_pattern, template}; a new rule is addable via config.
```

## Sign-offs

- [x] architect-review — 2026-07-14 12:55
- [x] test-writer — 2026-07-14 14:30
- [ ] python-coder — failed 2026-07-14 15:20
- [ ] test-runner — failed 2026-07-14 13:35
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

### 2026-07-14 14:30 — test-writer (status: ok)
feedback-id: fb_2026-07-14_476503d1
completion_manifest:
  tests_written: true
  tests_are_red: true
  covers_all_test_requirements: true
  no_syntax_errors: true

## Test Writer — Completion Report

### Tests Written
| File | Directory | Framework | Status |
|---|---|---|---|
| test_commit_classifier.py | unit_tests/ | pytest (unittest.TestCase) | 3 new tests added |
| test_mixed_set_detection.py | unit_tests/ | pytest (unittest.TestCase) | 3 new tests added |
| test_commit_patterns_config.py | unit_tests/ | pytest (unittest.TestCase) | 4 new tests added |

### Verification Run
- Command: `python -m pytest unit_tests/test_commit_classifier.py::TestCommitAgentInvokesClassifier unit_tests/test_mixed_set_detection.py::TestMixedCommitWarningSurfaced unit_tests/test_commit_patterns_config.py::TestRoutingConfigIsArraySchema -p no:scripts.ac_store.pytest_ac_enforcement -v --tb=short`
- Result: red (10 failures — expected; implementation not yet written)
- Note: With enforcement plugin active, tests show as XFAIL (exit 0) because the ACs have `work_status: todo`. This is the designed repo behavior — the enforcement plugin converts failures for in-progress ACs to informational xfail. The tests are genuinely failing internally (verified without plugin, exit 1). When python-coder implements the features, the tests will pass green.

### Notes
- All 10 new tests use `# covers: BO-1100a-N` / `# covers: BO-1100b-N` / `# covers: BO-1100c-N` tags so the enforcement plugin correctly tracks them.
- Existing 47 tests (pre-existing, all green) are untouched.
- The `test_ac_bo1100c2_new_rule_addable_via_config_path_param` test fails with `TypeError: classify_staged_files() got an unexpected keyword argument 'patterns_config_path'` — this confirms python-coder must add the `patterns_config_path` parameter.

red_baseline:
  - test_name: test_commit_agent_invokes_classifier
    file: unit_tests/test_commit_classifier.py
    error: "AssertionError: 'classify_staged_files' not found in commit.md content (commit.md Step 2 must invoke classify_staged_files() as the PRIMARY message-drafting path)"
  - test_name: test_ac_bo1100a3_commit_delegates_to_learner_on_unknown
    file: unit_tests/test_commit_classifier.py
    error: "AssertionError: 'maybe_propose_rule' not found in commit.md (specialist delegation absent from commit agent template)"
  - test_name: test_ac_bo1100a4_classifier_skipped_when_subject_already_approved
    file: unit_tests/test_commit_classifier.py
    error: "AssertionError: 'already approved' not found in commit.md (no guard exists to skip classifier when subject already approved)"
  - test_name: test_mixed_commit_warning_surfaced
    file: unit_tests/test_mixed_set_detection.py
    error: "AssertionError: 'detect_mixed_set' not found in commit.md (mixed-set library never invoked from commit agent template)"
  - test_name: test_ac_bo1100b2_warning_lists_all_filenames_per_group
    file: unit_tests/test_mixed_set_detection.py
    error: "AssertionError: 'new_hook.py' not found in 'Mixed staged set detected: unrelated groups present — tickets (TICKET-001.md), implementation code (2 files).' — warning only shows count, not individual filenames"
  - test_name: test_ac_bo1100b3_warning_offers_explicit_proceed_and_abort
    file: unit_tests/test_mixed_set_detection.py
    error: "AssertionError: 'proceed' not found in combined warning+recommendation string (current text uses 'split/confirm intentionally', not 'Proceed/Abort')"
  - test_name: test_routing_config_is_array_schema
    file: unit_tests/test_commit_patterns_config.py
    error: "AssertionError: {'_comment': ..., 'patterns': {...}} is not an instance of <class 'list'>"
  - test_name: test_ac_bo1100c1_each_entry_has_path_pattern_field
    file: unit_tests/test_commit_patterns_config.py
    error: "AssertionError: {'_comment': ..., 'patterns': {...}} is not an instance of <class 'list'>"
  - test_name: test_ac_bo1100c1_at_least_five_default_entries
    file: unit_tests/test_commit_patterns_config.py
    error: "AssertionError: {'_comment': ..., 'patterns': {...}} is not an instance of <class 'list'>"
  - test_name: test_ac_bo1100c2_new_rule_addable_via_config_path_param
    file: unit_tests/test_commit_patterns_config.py
    error: "TypeError: classify_staged_files() got an unexpected keyword argument 'patterns_config_path'"

### 2026-07-14 15:20 — python-coder (status: blocker)
feedback-id: fb_2026-07-14_fafa5f56
completion_manifest:
  commit_md_wired_to_classifier: true
  detect_mixed_set_filenames_listed: true
  proceed_abort_keywords_added: true
  patterns_config_path_param_added: true
  array_schema_config_converted:
    result: false
    reason: "Tests test_routing_config_is_array_schema, test_ac_bo1100c1_each_entry_has_path_pattern_field, and test_ac_bo1100c1_at_least_five_default_entries (TestRoutingConfigIsArraySchema) require commit_message_patterns.json to be a top-level JSON array, but pre-existing green tests in TestPatternsConfigFileExists (test_config_file_is_valid_json, test_config_file_has_patterns_key, test_config_patterns_cover_all_file_groups, test_all_patterns_contain_detail_placeholder) assert it is a dict with a 'patterns' key. Both sets read the same _PATTERNS_CONFIG_PATH. The two schemas are mutually exclusive — implementing the array schema breaks 4 pre-existing green tests."
    remediation: "Respawn test-writer to update TestPatternsConfigFileExists to accept the new array format (classification: test_drift — the pre-existing tests are stale relative to AC BO-1100c-1). After test-writer updates those 4 tests, python-coder can implement the array schema conversion without violating the TDD gate."
  no_previously_green_tests_broken: true

Made 7 of 10 red_baseline tests green (commit.md wired to classify_staged_files + detect_mixed_set + maybe_propose_rule; detect_mixed_set warning now lists individual filenames and recommendation contains explicit Proceed/Abort; patterns_config_path parameter added to classify_staged_files). Three red_baseline tests (test_routing_config_is_array_schema, test_ac_bo1100c1_each_entry_has_path_pattern_field, test_ac_bo1100c1_at_least_five_default_entries) cannot be made green without breaking 4 pre-existing passing tests in TestPatternsConfigFileExists — classification: test_drift. Remediation: respawn test-writer to update TestPatternsConfigFileExists to accept a JSON array (not dict), then respawn python-coder for the array schema conversion.

red_baseline_results:
  - test_name: test_commit_agent_invokes_classifier
    result: green
  - test_name: test_ac_bo1100a3_commit_delegates_to_learner_on_unknown
    result: green
  - test_name: test_ac_bo1100a4_classifier_skipped_when_subject_already_approved
    result: green
  - test_name: test_mixed_commit_warning_surfaced
    result: green
  - test_name: test_ac_bo1100b2_warning_lists_all_filenames_per_group
    result: green
  - test_name: test_ac_bo1100b3_warning_offers_explicit_proceed_and_abort
    result: green
  - test_name: test_routing_config_is_array_schema
    result: blocker — conflicts with pre-existing green tests in TestPatternsConfigFileExists (test_drift)
  - test_name: test_ac_bo1100c1_each_entry_has_path_pattern_field
    result: blocker — same conflict
  - test_name: test_ac_bo1100c1_at_least_five_default_entries
    result: blocker — same conflict
  - test_name: test_ac_bo1100c2_new_rule_addable_via_config_path_param
    result: green

### 2026-07-14 12:55 — architect-review (status: ok)
feedback-id: fb_2026-07-14_cf0410e9
completion_manifest:
  blast_radius_assessed: true
  classification_made: true
  acceptance_adjustments_noted: true
  requires_adr_set: true
Classified as SMALL. Six files (1 over the 5-file threshold), all in the single build_orchestration component with no cross-module boundary crossing and no always-large triggers. Classification uses the judgment-call clause: 2 of 6 files are tests, the other 4 are tightly-coupled commit-pipeline files (1 agent template, 1 config, 2 scripts that already carry 150 passing tests). The change is a pure wiring fix — the library exists; the work invokes it. Two acceptance adjustments logged: (1) the config loader must handle the legacy flat-object schema gracefully on upgrade; (2) classify_staged_files() must be the PRIMARY Step 2 path, not a fallback after free-hand drafting. No ADR required (1 component, no always-large trigger). escalation: none.

### 2026-07-14 13:35 — test-runner (status: blocker)
feedback-id: fb_2026-07-14_4114c85a
completion_manifest:
  test_suite_executed: true
  all_tests_passing:
    result: false
    reason: "3 of 77 tests fail in TestRoutingConfigIsArraySchema (test_routing_config_is_array_schema, test_ac_bo1100c1_each_entry_has_path_pattern_field, test_ac_bo1100c1_at_least_five_default_entries). config/commit_message_patterns.json is still a dict schema; tests require a top-level JSON array per AC BO-1100c-1. Pre-existing TestPatternsConfigFileExists tests assert the dict schema — the two test classes are mutually exclusive."
    remediation: "Respawn test-writer to update TestPatternsConfigFileExists to accept the new array schema (classification: test_drift). After test-writer updates those 4 tests to be array-schema-aware, respawn python-coder to implement the config conversion without breaking the TDD gate."
  failure_report_structured: true

Ran 77 tests via pytest (no enforcement plugin). 74 passed, 3 failed — all failures are AssertionError in TestRoutingConfigIsArraySchema asserting top-level list schema. The 7 red_baseline tests that python-coder fixed are now green. The 3 remaining failures are the known test_drift conflict python-coder flagged: respawn test-writer first to update TestPatternsConfigFileExists, then respawn python-coder for the array schema conversion.
