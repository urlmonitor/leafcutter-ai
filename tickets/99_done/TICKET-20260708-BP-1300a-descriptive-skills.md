---
title: "Self-description validation: descriptive_only skills_invoked entries (BP-1300a)"
status: todo
components:
- build-pipeline
created: '2026-07-08'
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_adr: false
requires_diagram: false
source_ac: BP-1300a-1
files_touched:
- scripts/build_phases.py
- config/agent_registry.json
- unit_tests/build/test_self_description_descriptive_only.py
- scripts/registry_validator.py
agents:
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
---

# Self-description validation: descriptive_only skills_invoked entries (BP-1300a)

## Actor / Goal

In order to clear the live CI red without discarding AC-mandated metadata, we need
`validate_agent_self_description` to distinguish an INTENTIONAL capability-documentation
`skills_invoked` entry (which has no deployed skill dir by design) from a genuinely
dangling/typo'd skill_id — so the build fails on true dangling pointers but passes on
marked descriptive entries.

## Context

`config/agent_registry.json` sets `self_description_enforcement: error`. Two entries —
`run-tests` (python-coder) and `direct-write` (documentation-expert) — describe INLINE
capabilities (python-coder runs tests inline; documentation-expert writes docs directly),
not deployed skills, so no `templates/skills/{run-tests,direct-write}/` dir exists. In
error mode `validate_agent_self_description` treats them as unresolvable and fails the
build (exit 1) — the live CI red and the premise of the restore-ci-test-baseline ticket.

AC **INF-600d-1** (done) explicitly requires python-coder's `skills_invoked` to carry a
`run-tests` entry documenting that capability. So removing the entry regresses INF-600d-1
(confirmed by pr-review on TICKET-20260707-BP-100m-1). The chosen resolution: add a
`descriptive_only: true` marker to such entries; the validator skips skill-dir resolution
for marked entries but still hard-fails on any UNMARKED unresolvable skill_id. A marked
entry is not "dangling" (it is intentional + documented), so BP-1300a's guardrail intent
is preserved — only genuine dangling pointers fail.

## AC References

Implements / resolves under **BP-1300** (docs/acceptance-criteria/build_pipeline/BP-1300-unmaskable-guardrails/):
- BP-1300a-1 — an UNMARKED unresolvable skills_invoked skill_id fails the build deterministically (unchanged intent; the guardrail still fires on true dangling).
- BP-1300a-1-i — resolves the `run-tests` / `direct-write` case by marking them `descriptive_only: true` (they document inline capabilities; the fix is to mark, not delete — preserving INF-600d-1).
- BP-1300a-1-ii — the verdict is independent of stale deployed `.claude/skills/` artifacts (validate against canonical source + the marker).

## Acceptance Criteria

```gherkin
Scenario: unmarked unresolvable skill_id still fails (BP-1300a-1)
  Given a skills_invoked entry whose skill_id resolves to no templates/skills/<id>/
    and which is NOT marked descriptive_only
  When build.py runs with self_description_enforcement=error
  Then the build exits non-zero and names the offending agent + skill_id

Scenario: descriptive_only entry passes (BP-1300a-1-i)
  Given a skills_invoked entry marked descriptive_only: true whose skill_id has no
    deployed skill dir
  When build.py runs with self_description_enforcement=error
  Then self-description validation does NOT flag it and the build proceeds

Scenario: run-tests and direct-write are marked and the real build passes
  Given config/agent_registry.json marks run-tests (python-coder) and direct-write
    (documentation-expert) as descriptive_only: true
  When build.py runs (error mode) on the real repo
  Then self-description validation reports all agents pass (no dangling-skill_id error)

Scenario: verdict independent of stale deployed artifacts (BP-1300a-1-ii)
  Given a descriptive_only entry and a stale .claude/skills/ tree
  When validation runs
  Then the pass/fail verdict is the same regardless of the deployed tree (source + marker only)
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| BP-1300a-1 | unit_tests/build/test_self_description_descriptive_only.py:TestUnmarkedUnresolvableFails::test_ac_bp1300a_1_unmarked_unresolvable_fails | Existing resolution block in validate_agent_self_description (scripts/build_phases.py ~line 1757) fires for unmarked entries — preserved unchanged | |
| BP-1300a-1-i | unit_tests/build/test_self_description_descriptive_only.py:TestDescriptiveOnlyPasses::test_ac_bp1300a_1i_descriptive_only_passes | Added `if inv.get("descriptive_only") is True: continue` guard in validate_agent_self_description after the `if not skill_id` check (scripts/build_phases.py) | |
| BP-1300a-1-ii | unit_tests/build/test_self_description_descriptive_only.py:TestVerdictIndependentOfStaleDeploy::test_ac_bp1300a_1ii_verdict_independent_of_stale_deployed_artifacts | descriptive_only guard fires before the in_package/in_project resolution check — verdict driven by marker, not deployed artifact | |

## Implementation Tasks

- [ ] Add `descriptive_only: true` support to the `skills_invoked` schema handling in `validate_agent_self_description` (scripts/build_phases.py): skip skill-dir resolution for marked entries; keep hard-failing unmarked unresolvable skill_ids.
- [ ] Mark `run-tests` (python-coder) and `direct-write` (documentation-expert) `skills_invoked` entries with `descriptive_only: true` in config/agent_registry.json (keep the entries — INF-600d-1).
- [ ] Confirm `python build.py` (error mode) now reports self-description all-pass on the real repo.
- [ ] Add `unit_tests/build/test_self_description_descriptive_only.py` covering the four scenarios (behavioral: run the validator with marked/unmarked entries; assert pass/fail + message).

## Risk & Safety

- Touches money? No.
- Touches data? No — build-time validation only.
- Reversibility? Fully reversible. Risk: over-broad skip (marking hiding a real dangling id) — mitigated by requiring the explicit `descriptive_only: true` marker per entry; unmarked entries still fail.

## Sign-offs

- [x] test-writer — 2026-07-08 10:30
- [x] python-coder — 2026-07-08 11:00
- [x] test-runner — 2026-07-08 12:00
- [x] pr-reviewer — 2026-07-08 14:00
- [ ] commit
- [ ] pull-request

## Comments

### 2026-07-08 10:30 — test-writer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  tests_written: true
  tests_red_confirmed: true
  ac_coverage_table_filled: true
  regression_guard_present: true

4 test stubs written at unit_tests/build/test_self_description_descriptive_only.py.
Verification run produced exit 1 (non-zero) — 4 failures, 2 expected-green guards.
The two currently-passing tests (regression guard + intermediate-state integration guard)
are not in the red_baseline; they guard against regressions after the fix lands.

red_baseline:
  - test_name: TestDescriptiveOnlyPasses::test_ac_bp1300a_1i_descriptive_only_passes
    file: unit_tests/build/test_self_description_descriptive_only.py
    error: "AssertionError: Expected validator NOT to flag descriptive_only: true entry 'inline-capability', but got error_count=1. python-coder must add the ``if inv.get('descriptive_only') is True: continue`` guard inside the skills_invoked resolution loop in validate_agent_self_description."
  - test_name: TestRealRegistryEntriesMarked::test_ac_scenario3_python_coder_has_run_tests_marked
    file: unit_tests/build/test_self_description_descriptive_only.py
    error: "AssertionError: python-coder skills_invoked must contain a 'run-tests' entry (required by INF-600d-1 to document the inline test-running capability). Add: {\"skill_id\": \"run-tests\", \"mode\": \"conditional\", \"descriptive_only\": true} to python-coder.skills_invoked."
  - test_name: TestRealRegistryEntriesMarked::test_ac_scenario3_documentation_expert_has_direct_write_marked
    file: unit_tests/build/test_self_description_descriptive_only.py
    error: "AssertionError: documentation-expert skills_invoked must contain a 'direct-write' entry (documents the inline doc-writing capability per INF-600d-1). Add: {\"skill_id\": \"direct-write\", \"mode\": \"conditional\", \"descriptive_only\": true} to documentation-expert.skills_invoked."
  - test_name: TestVerdictIndependentOfStaleDeploy::test_ac_bp1300a_1ii_verdict_independent_of_stale_deployed_artifacts
    file: unit_tests/build/test_self_description_descriptive_only.py
    error: "AssertionError: Expected error_count == 0 without stale deployed artifact and descriptive_only: true, but got error_count=1. The validator must not rely on .claude/skills/ resolution for descriptive_only entries."

not_in_red_baseline:
  - test_name: TestUnmarkedUnresolvableFails::test_ac_bp1300a_1_unmarked_unresolvable_fails
    status: passes_now
    note: "Regression guard — asserts existing validator behavior is preserved; intentionally green"
  - test_name: TestRealRegistryEntriesMarked::test_ac_scenario3_real_validation_reports_zero_errors
    status: passes_now
    note: "Intermediate-state guard — currently passes because run-tests/direct-write entries absent; becomes a blocker once entries are added without descriptive_only support"

Validator seam python-coder must extend:

  function: validate_agent_self_description (scripts/build_phases.py, ~line 1739)
  location: inside the ``for inv in skills_invoked:`` loop, AFTER ``if not skill_id: continue``
  change: ADD the following 2 lines:
    if inv.get("descriptive_only") is True:
        continue  # Intentional inline capability — no skill dir required
  rationale: strict identity test (``is True``) prevents accidental skipping when
    the key holds a string, integer, or None.

Registry additions python-coder must make (config/agent_registry.json):
  python-coder.skills_invoked: ADD {"skill_id": "run-tests", "mode": "conditional", "descriptive_only": true}
  documentation-expert.skills_invoked: ADD {"skill_id": "direct-write", "mode": "conditional", "descriptive_only": true}

### 2026-07-08 11:00 — python-coder (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  descriptive_only_guard_added: true
  run_tests_entry_marked: true
  direct_write_entry_marked: true
  tests_green: true
  real_build_error_mode_passes: true
  ruff_clean: true

Validator change: added `if inv.get("descriptive_only") is True: continue` guard in
`validate_agent_self_description` (scripts/build_phases.py) inside the
`for inv in skills_invoked:` loop, after the existing `if not skill_id: continue`
guard. The strict `is True` identity check prevents accidental skipping when the
key holds a string, int, or None. Updated docstring and DECISION HISTORY to
document the new marker semantics per INF-600d-1.

Registry: added `{"skill_id": "run-tests", "mode": "conditional", "descriptive_only": true}`
to python-coder and `{"skill_id": "direct-write", "mode": "conditional", "descriptive_only": true}`
to documentation-expert in config/agent_registry.json. Both entries were new (not pre-existing);
no duplicates introduced.

Real build: `python build.py --target-dir /tmp/bp1300a-check --self-description-enforcement error`
exits 0. Output: "Self-description validation: all agents pass." No
"unresolvable skills_invoked skill_id" error for run-tests or direct-write.

red_baseline_results:
  - test_name: TestDescriptiveOnlyPasses::test_ac_bp1300a_1i_descriptive_only_passes
    result: green
  - test_name: TestRealRegistryEntriesMarked::test_ac_scenario3_python_coder_has_run_tests_marked
    result: green
  - test_name: TestRealRegistryEntriesMarked::test_ac_scenario3_documentation_expert_has_direct_write_marked
    result: green
  - test_name: TestVerdictIndependentOfStaleDeploy::test_ac_bp1300a_1ii_verdict_independent_of_stale_deployed_artifacts
    result: green

ruff: auto-fixed 2 unused imports (tempfile, pytest) left in test file by test-writer;
no test logic changed; all 6 tests remain green.

### 2026-07-08 12:00 — test-runner (status: ok)
feedback-id: fb_2026-07-08_cbd5ba96
completion_manifest:
  test_suite_executed: true
  all_tests_passing: true
  failure_report_structured: true

Ruff: clean (exit 0). New suite (test_self_description_descriptive_only.py): 6/6 passed. Collision-guard suite (test_deploy_collision_guard.py): 14/14 passed. Full suite: 101 failed / 1583 passed / 51 skipped / 1 xfailed / 1 collection-error (pre-existing import error in test_link_feedback_resolve.py, not introduced by this branch) — count DROPPED from ~102 baseline to 101, consistent with self-description tests now passing in error mode; no new failures detected. Real build (error mode, --self-description-enforcement error): exit 0, output "Self-description validation: all agents pass.".

### 2026-07-08 15:00 — python-coder (status: ok) [M-1 follow-on fix]
feedback-id: (submit-failed)
completion_manifest:
  m1_fix_implemented: true
  descriptive_only_exclusion_in_xref: true
  new_tests_added: true
  no_run_tests_warning: true
  no_direct_write_warning: true
  files_touched_updated: true
  ruff_clean: true

M-1 fix: extended the descriptive_only exemption to `check_skills_invoked_xref`
in `scripts/registry_validator.py`. The `declared_ids` set comprehension now skips
entries where `e.get("descriptive_only") is not True` (strict identity test, mirroring
`validate_agent_self_description`). After the BP-1300a fix marked `run-tests` (python-coder)
and `direct-write` (documentation-expert) as `descriptive_only: true`, the xref checker
still emitted advisory `[WARNING] <agent>: skills_invoked declares '<id>' but no reference
found in template body` for both — because they legitimately have no template body reference
(inline capabilities, not deployed skills). The fix suppresses those spurious warnings while
preserving Direction 2 warnings for all non-descriptive unreferenced entries.

Added 2 tests to `unit_tests/build/test_self_description_descriptive_only.py`
(class `TestCheckSkillsInvokedXrefDescriptiveOnly`):
  - `test_descriptive_only_entry_suppresses_direction2_warning` — asserts NO xref warning
    for a `descriptive_only: true` entry with no template body reference (green after fix).
  - `test_non_descriptive_unreferenced_entry_still_warns` — asserts the warning STILL fires
    for a non-descriptive unreferenced entry (guards both directions).

Added `scripts/registry_validator.py` to ticket frontmatter `files_touched`.

Verification:
  - pytest unit_tests/build/ -q: 22 passed (was 20; +2 new tests, all green)
  - ruff check scripts/ unit_tests/: exit 0, all checks passed
  - python build.py --self-description-enforcement error: exit 0, "all agents pass"
  - No advisory warning for 'run-tests' or 'direct-write' appears in stdout

Re-verify note: this follow-on touches a previously-unseen file (registry_validator.py)
that was not in scope when test-runner and pr-reviewer signed off. A re-verify of both
phases is warranted before the commit phase proceeds.

### 2026-07-08 14:00 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  is_true_identity_check_confirmed: true
  unmarked_guardrail_intact: true
  registry_no_duplicates: true
  consumer_analysis_complete: true
  no_tests_weakened: true
  scope_clean: true

No high-confidence blockers found. One medium advisory: registry_validator.py
check_skills_invoked_xref (called at build time) processes both python-coder and
documentation-expert as portable agents. The new run-tests and direct-write
entries will appear in declared_ids but likely have no matching template-body
reference in the recognized pattern formats (path, directive, or Skill-tool
invocation), so the xref check will emit advisory [WARNING] lines for each.
This is non-blocking (the function's return value is printed-only, not added
to the errors list — confirmed at registry_validator.py line 124 comment and
lines 126-128). No fix required before merge; a follow-up could suppress xref
warnings for descriptive_only entries in registry_validator.check_skills_invoked_xref.

### 2026-07-08 — test-writer (status: ok) [M-2 guard tests]
feedback-id: (submit-failed)
completion_manifest:
  m2_guard_tests_added: true
  validator_parametrized: true
  xref_guard_added: true
  all_tests_green: true
  ruff_clean: true

M-2 guard tests added to unit_tests/build/test_self_description_descriptive_only.py
to lock the strict ``is True`` identity check against regression.

New tests added (all GREEN immediately — they assert the existing correct behavior):

validate_agent_self_description guard (parametrized, class TestMisTypedMarkerNotExemptedValidator):
  - test_mistyped_descriptive_only_does_not_exempt_validator[true-string-true]
    descriptive_only: "true" (string) on unresolvable skill_id → error_count > 0
  - test_mistyped_descriptive_only_does_not_exempt_validator[1-int-one]
    descriptive_only: 1 (int) on unresolvable skill_id → error_count > 0
  - test_mistyped_descriptive_only_does_not_exempt_validator[None-none]
    descriptive_only: None on unresolvable skill_id → error_count > 0

check_skills_invoked_xref guard (class TestCheckSkillsInvokedXrefDescriptiveOnly):
  - test_string_descriptive_only_does_not_suppress_xref_warning
    descriptive_only: "true" (string) with no template body reference → Direction 2
    warning IS emitted (entry is NOT exempted by the xref guard)

All 12 tests pass (existing 8 + new 4). Ruff: exit 0. The real functions are
exercised directly (validate_agent_self_description from build_phases,
check_skills_invoked_xref from registry_validator) — no reimplementations.

Verification:
  command: python -m pytest unit_tests/build/test_self_description_descriptive_only.py -v --tb=short
  result: 12/12 passed (exit 0)
