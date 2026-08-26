---
title: "Presence-only assertions stop counting as coverage: re-author the journal test, then gate the shape"
status: done
components:
  - build_pipeline
created: 2026-08-17
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
source_ac: BP-1100b-5
ac_coverage:
  - BP-1100b-4
  - BP-1100b-5
ac_traceability:
  l2:
    - BP-1100b-4
    - BP-1100b-5
  l3: []
  ac_path: docs/acceptance-criteria/build_pipeline/BP-1100-phantom-done-prevention/
change_target: pipeline
risk_surface: contract_boundary
complexity: high
roadmap_phase: phase_1
advances_current_outcome: true
documentation_required: true
files_touched:
  - templates/scripts/commit_guardian/check_presence_only_assertions.py
  - templates/scripts/commit_guardian/_presence_only_scanner.py
  - templates/scripts/commit_guardian/commit_guardian.json
  - docs/pre-commit-hooks.md
  - unit_tests/_workflow_engine_harness.py
  - unit_tests/workflows/test_bo_1000c_1a.py
  - templates/workflows-js/finalize-feature.js
  - unit_tests/commit_guardian/test_bp_1100b_5.py
  - unit_tests/workflows/test_bp_1100b_4.py
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: needed
  pr-reviewer: needed
  ac-validator: needed
  ac-fulfillment-gate: needed
  commit: needed
  pull-request: needed
---

# 09: A test can no longer prove a guard works by grepping for its name

## Actor / Goal

As this repository's defence against phantom-done, I want the one confirmed grep-only
test re-authored into an executed assertion **and** a pre-commit gate that rejects newly
added presence-only assertions over workflow and commit-guardian source — so that
"covered" stops being satisfiable by a regex that stays green over unreachable code.

## Remediation Context (scope refresh 2026-08-17)

This is the epic's own thesis turned on the epic's own evidence base. Every other ticket
here fixes a guard that reported a pass it had not earned; this one fixes the *tests* that
let those passes stand.

**The confirmed incumbent (BP-1100b-4).** `unit_tests/workflows/test_bo_1000c_1a.py` is
entirely `read_text()` + regex over `templates/workflows-js/finalize-feature.js`: it
asserts a journal-appending function is *declared* and that its declaration mentions an
append mode. It is green today with no evidence any journal record has ever been written
by a real finalize run. The append sits inside a `try`; the `catch` only logs — so under
an engine that exposes no filesystem primitive, the append is swallowed and the run still
reports success.

**The hidden prerequisite — read this before scheduling.** The AC is explicit that the
harness fix comes FIRST. A reviewer executed `run_workflow_under_e2()` against
`finalize-feature.js` and it wrote 9 journal records in step order with **zero
implementation** — because `unit_tests/_workflow_engine_harness.py` exposes
`require('fs')`, which per ADR-017 the real E2 engine does not. Authoring the re-authored
journal tests against today's harness would certify a behaviour production cannot perform.
That is a phantom-done trap *inside* the phantom-done remediation.

**The ratchet (BP-1100b-5).** A new commit-guardian hook reading **staged hunks only**.
A whole-file scan would fire on the 46 pre-existing violations counted across
`unit_tests/workflows/` and `unit_tests/commit_guardian/` and make the hook's own
introducing commit unmergeable. Nothing new lands; the backlog is cleaned by a separate
sweep.

**Why these two travel together.** `-5` is the detector, `-4` is its first customer and
its calibration fixture. Building the detector with no in-tree offender to calibrate
against reproduces the very failure mode it targets; fixing the offender alone leaves the
class open. The two edit disjoint files, so they are one coherent diff, not a collision.

**This gate will indict work already in this epic.** Its rule already matches
`unit_tests/build_guards/test_ci_test_gate.py` (from dropped ticket 05) and
`test_deploy_collision_guard.py:741` (`assert 'Workflow("build-feature"' in content`,
ticket 06's stand-in). Because the scope is staged hunks, those are not blockers — but
tickets 07, 08 and 06 must write behavioural proofs from the start rather than expect a
waiver.

## AC References

Resolves **BP-1100b-4** and **BP-1100b-5**. Verbatim Gherkin in
`docs/acceptance-criteria/build_pipeline/BP-1100-phantom-done-prevention/`; the YAML is
the source of truth.

- [ ] AC-1: the declaration regex is no longer the only coverage of run-progress journaling (BP-1100b-4)
- [ ] AC-2: a test executes the finalize workflow under the harness and asserts one record per completed step, in step order, still present at run end (BP-1100b-4)
- [ ] AC-3: a run in which the append cannot happen FAILS at least one test instead of passing (BP-1100b-4)
- [ ] AC-4: renaming the journal helper without changing what is journaled leaves the tests green (BP-1100b-4)
- [ ] AC-5: the harness exposes exactly the engine-injected globals and no module loader or filesystem primitive (BP-1100b-4)
- [ ] AC-6: an unwaived newly-added presence-only assertion is reported, naming test file, symbol and scanned source (BP-1100b-5)
- [ ] AC-7: both the substring form and the regex-declaration form are matched (BP-1100b-5)
- [ ] AC-8: a `# presence-only: <reason>` waiver with a non-empty reason suppresses and is listed; an empty reason does not suppress (BP-1100b-5)
- [ ] AC-9: pre-existing assertions in untouched files are not reported — staged hunks only (BP-1100b-5)
- [ ] AC-10: the documentation-marker non-target is not over-matched (BP-1100b-5)

## Test Requirements

```yaml
tests:
  - name: test_harness_exposes_only_the_engine_injected_globals
    file: unit_tests/workflows/test_bp_1100b_4.py
    covers: [BP-1100b-4]
    framework: pytest
    type: behavioral
    asserts: A workflow body run under run_workflow_under_e2() can reach exactly the globals the real engine injects (agent, parallel, pipeline, phase, log, args, workflow, budget) and nothing else — enumerated from the workflow body at runtime, not asserted against a copy of the list.
  - name: test_harness_exposes_no_module_loader_to_the_workflow_body
    file: unit_tests/workflows/test_bp_1100b_4.py
    covers: [BP-1100b-4]
    framework: pytest
    type: behavioral
    asserts: A workflow body that attempts to reach a module loader or a filesystem primitive under the harness is refused exactly as the real engine refuses it.
  - name: test_filesystem_dependent_journaling_produces_zero_records_under_the_harness
    file: unit_tests/workflows/test_bp_1100b_4.py
    covers: [BP-1100b-4]
    framework: pytest
    type: behavioral
    asserts: A workflow whose journaling depends on a filesystem primitive produces zero journal records under the engine-faithful harness — the calibration that proves the harness now reproduces the production failure.
  - name: test_one_journal_record_is_appended_per_completed_step
    file: unit_tests/workflows/test_bo_1000c_1a.py
    covers: [BP-1100b-4]
    framework: pytest
    type: behavioral
    asserts: Executing the finalize workflow under the engine-faithful harness produces exactly one journal record per completed step — cardinality asserted against the steps the run actually completed, not against a hardcoded count.
  - name: test_journal_records_appear_in_step_order
    file: unit_tests/workflows/test_bo_1000c_1a.py
    covers: [BP-1100b-4]
    framework: pytest
    type: behavioral
    asserts: The journal records produced by that executed run appear in the order the steps completed.
  - name: test_journal_records_are_still_present_when_the_run_ends
    file: unit_tests/workflows/test_bo_1000c_1a.py
    covers: [BP-1100b-4]
    framework: pytest
    type: behavioral
    asserts: The journal records written during the run are still readable after the workflow terminates, so a run that journals into a location the workflow later removes does not count as journaling.
  - name: test_run_that_cannot_append_fails_instead_of_passing
    file: unit_tests/workflows/test_bo_1000c_1a.py
    covers: [BP-1100b-4]
    framework: pytest
    type: behavioral
    asserts: A run in which the append cannot happen in the execution environment — the append swallowed by the surrounding error handler — fails at least one of the journal tests rather than passing with zero records.
  - name: test_renaming_the_journal_helper_leaves_the_tests_green
    file: unit_tests/workflows/test_bo_1000c_1a.py
    covers: [BP-1100b-4]
    framework: pytest
    type: behavioral
    asserts: Renaming the journal-appending function, or rewording its declaration, without changing what is journaled leaves every journal test green — proving the coverage binds to behaviour rather than to source text.
  - name: test_unwaived_substring_presence_assertion_is_reported_with_file_symbol_and_source
    file: unit_tests/commit_guardian/test_bp_1100b_5.py
    covers: [BP-1100b-5]
    framework: unittest
    type: behavioral
    asserts: Executing the hook against a synthesized staged diff that adds a substring presence assertion over a scanned-source file reports a violation naming the test file, the asserted symbol, and the source file the assertion scans.
  - name: test_regex_declaration_presence_assertion_is_also_reported
    file: unit_tests/commit_guardian/test_bp_1100b_5.py
    covers: [BP-1100b-5]
    framework: unittest
    type: behavioral
    asserts: The same executed hook reports the regular-expression declaration form (a match that a named function is declared in a scanned source), not only the substring form.
  - name: test_report_states_the_unreachable_code_rationale_and_names_the_waiver
    file: unit_tests/commit_guardian/test_bp_1100b_5.py
    covers: [BP-1100b-5]
    framework: unittest
    type: behavioral
    asserts: The hook's emitted report states that a presence-only assertion over workflow or commit-guardian source stays green on unreachable code and is therefore not coverage, and names the waiver comment as the deliberate-acceptance route.
  - name: test_waived_assertion_is_not_reported_and_its_reason_is_listed
    file: unit_tests/commit_guardian/test_bp_1100b_5.py
    covers: [BP-1100b-5]
    framework: unittest
    type: behavioral
    asserts: "An added assertion preceded by `# presence-only: <reason>` with a non-empty reason is not reported, and the waiver together with its reason appears in the executed hook's output."
  - name: test_waiver_with_an_empty_reason_does_not_suppress_the_violation
    file: unit_tests/commit_guardian/test_bp_1100b_5.py
    covers: [BP-1100b-5]
    framework: unittest
    type: behavioral
    asserts: A waiver comment carrying an empty or whitespace-only reason leaves the violation reported, so the marker cannot become a silent suppression list.
  - name: test_presence_assertion_over_an_unscanned_file_is_not_reported
    file: unit_tests/commit_guardian/test_bp_1100b_5.py
    covers: [BP-1100b-5]
    framework: unittest
    type: behavioral
    asserts: An added presence-only assertion over a file matched by none of the configured scanned-source globs produces no violation.
  - name: test_preexisting_assertions_in_untouched_files_are_not_reported
    file: unit_tests/commit_guardian/test_bp_1100b_5.py
    covers: [BP-1100b-5]
    framework: unittest
    type: behavioral
    asserts: Run against a repository that already contains presence-only assertions over the scanned sources, with a staged change touching none of them, the hook reports nothing — proving it reads staged hunks rather than whole files.
  - name: test_new_violation_reported_regardless_of_author_or_source_co_modification
    file: unit_tests/commit_guardian/test_bp_1100b_5.py
    covers: [BP-1100b-5]
    framework: unittest
    type: behavioral
    asserts: A newly added presence-only assertion is reported whether or not the same staged change also modifies the source file the assertion scans, and irrespective of the authoring agent.
  - name: test_documentation_marker_assertion_is_not_over_matched
    file: unit_tests/commit_guardian/test_bp_1100b_5.py
    covers: [BP-1100b-5]
    framework: unittest
    type: behavioral
    asserts: "Calibration against the named non-target: an added assertion that a literal AC id appears in a workflow source (the documentation-marker shape at unit_tests/workflows/test_bo_1000a_2_i.py ~L166) is not reported."
  - name: test_scanned_source_globs_are_read_from_the_guardian_config
    file: unit_tests/commit_guardian/test_bp_1100b_5.py
    covers: [BP-1100b-5]
    framework: unittest
    type: behavioral
    asserts: Changing the configured scanned_source_globs changes which files the executed hook reports on — proving the glob set is data read from the guardian config rather than a hardcoded copy in the hook.
  - name: test_deployed_hook_runs_and_reports_after_build
    file: unit_tests/commit_guardian/test_bp_1100b_5.py
    covers: [BP-1100b-5]
    framework: unittest
    type: behavioral
    asserts: After build.py deploys, the hook copy under scripts/commit_guardian/ is invoked as the pre-commit runner invokes it and reports the violation — proving the hooks_manifest entry and the deploy manifest are both wired, not just the templates/ source.
```

## Implementation Notes

```yaml
reference_file_path: templates/scripts/commit_guardian/commit_guardian.json
n_location_rule: '2'
post_write_commands:
  - python scripts/build.py --target-dir .
  - python -m pytest unit_tests/workflows/ -q
required_skills:
  - python-coder
config_schema_fragment:
  presence_only_assertion_guard:
    type: object
    description: Per-hook config key for the staged-hunk presence-only assertion gate. Declares
      whether the gate is enabled, the scanned-source glob set the rule applies to, and the
      waiver marker string. The globs are DATA, read by the hook from this key — the hook must
      not carry its own copy.
    properties:
      enabled: {type: boolean}
      scanned_source_globs: {type: array, items: {type: string}}
      waiver_marker: {type: string}
constraints:
  - 'ORDERING — the harness fidelity change comes FIRST. Authoring the re-authored journal
    tests against today''s harness ships a test that certifies a behaviour the production
    engine cannot perform: a reviewer already executed run_workflow_under_e2() against
    finalize-feature.js and it wrote 9 journal records in step order, present at run end,
    with zero implementation. Do not author scenario 1 until scenario 2 holds.'
  - SHARED TEST INFRASTRUCTURE — unit_tests/_workflow_engine_harness.py is depended on by every
    workflow test. Making it engine-faithful will turn other currently-green workflow tests red.
    Those must be triaged and re-authored inside this same diff. Re-admitting require(), a module
    loader, or a filesystem primitive to the harness in order to keep another test green is a
    violation of this AC, not a fix.
  - The injected-globals set must be declared ONCE and read by the harness, not duplicated as a
    literal in the harness and again in the runner; a second copy is free to drift from ADR-017
    and from the real engine.
  - The correct end state for the journal may be either a journal that works under the
    injected-globals contract or a journal that is removed — the assignee decides. What is NOT
    acceptable is a journal-append call whose failure is swallowed by the surrounding catch and
    reported as a successful run.
  - 'IMPLEMENTATION SURFACE for BP-1100b-5: a new hook script at
    templates/scripts/commit_guardian/check_presence_only_assertions.py. The doc_links entries
    under unit_tests/ are CALIBRATION EXAMPLES, not the thing being built.'
  - 'REGISTRATION SURFACE: the guardian config is templates/scripts/commit_guardian/commit_guardian.json
    (the 1181-line file holding hooks_manifest). There is NO config/commit_guardian.json in this
    repo, and templates/commit-guardian/commit_guardian.json is a different, much smaller file
    that is NOT the registration surface.'
  - 'n_location_rule ''2'' means BOTH locations in that config: (a) the per-hook config key
    carrying enabled / scanned_source_globs / waiver_marker, and (b) the hooks_manifest entry.
    The config key alone is INERT — the hooks_manifest entry is the gate that actually runs. A
    hook registered in only one of the two is a no-op that reads as shipped.'
  - 'THREE-WAY REGISTRATION per the create-hook skill: hook script + guardian config (both
    locations) + a row in the hook documentation index docs/pre-commit-hooks.md. The change must
    also keep check_hook_parity green.'
  - 'DEPLOYED-LAYOUT VERIFICATION: the hook runs from the deployed layout under
    scripts/commit_guardian/, not from templates/. Any module it imports must be in the build
    deploy manifest for that directory, and acceptance must include running the DEPLOYED hook
    after build.py against a real staged diff. A templates-only edit leaves the running gate
    unchanged, and a missing deploy entry raises ModuleNotFoundError at hook runtime.'
  - 'SCOPE IS STAGED HUNKS ONLY. A whole-file scan fires on the 46 pre-existing violations
    counted across unit_tests/workflows/ and unit_tests/commit_guardian/ and makes the hook''s
    own introducing commit unmergeable. The rule is a ratchet: nothing new lands, and the
    backlog is cleaned by a separate sweep.'
  - The rule must match BOTH the substring form and the regular-expression declaration form. A
    substring-only implementation misses the second confirmed incumbent.
  - The rule must NOT report the named non-target at unit_tests/workflows/test_bo_1000a_2_i.py
    (~L166), which asserts the literal AC id 'BO-1000a-2-i' appears in finalize-feature.js — a
    documentation-marker requirement, not a behavioural claim. Calibrate against it explicitly.
  - 'The waiver is `# presence-only: <reason>` with a NON-EMPTY reason. Accepted waivers and
    their reasons must be listed in the check''s own output so the accumulated waivers are
    readable in one place.'
  - The scanned-source glob set must be read from the guardian config key, never hardcoded in
    the hook script.
  - 'SELF-CONSISTENCY: this hook''s own coverage must execute the hook against a synthesized
    staged diff. A test asserting that a symbol appears in check_presence_only_assertions.py
    would be an instance of the exact defect the hook exists to reject.'
  - 'SERIALIZATION — commit_guardian.json: also edited by ticket 08 (BP-100k-3, drift-gate
    exemption registry). These two MUST NOT run concurrently; whichever lands second rebases
    onto the first rather than re-writing the whole config object.'
  - 'SERIALIZATION — finalize-feature.js: also edited by ticket 04 (FIN-100e auto-ticketing
    decision). These two MUST NOT run concurrently.'
  - 'Must follow the repo error-handling policy: specific-exception try/except around git, file,
    subprocess and JSON I/O, log at WARNING or higher or re-raise; no bare or silent excepts.'
```

## Out of Scope

- Sweeping the 46 pre-existing presence-only violations. The rule is a ratchet; the
  backlog is a separate follow-up.
- `FIN-100c-14` ("recovery tests assert observable behavior, not brittle source-substring
  counts") is the same defect class but belongs to the unbuilt FIN-100c-4 review-followup
  family. It stays with that family and will be caught mechanically by this gate.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? The hook is revertible via config. The harness change is not trivially
  revertible once other workflow tests are re-authored against it.
- Blast radius: **highest in this epic.** `_workflow_engine_harness.py` backs every
  workflow test, and a new pre-commit hook affects every commit repo-wide. Both risks are
  bounded deliberately — the harness change is contained in one diff with its fallout
  triaged inside it, and the hook reads staged hunks only.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| BP-1100b-4 | | | |
| BP-1100b-5 | | | |

## Sign-offs

- [ ] architect-review
- [x] test-writer — 2026-08-18 18:05
- [ ] python-coder — failed 2026-08-18 19:40
- [ ] test-runner
- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] ac-validator
- [ ] ac-fulfillment-gate
- [ ] commit
- [ ] pull-request

## Comments

### 2026-08-18 18:05 — test-writer (status: ok)
feedback-id: fb_2026-08-18_26e43b9e
completion_manifest:
  harness_fidelity_tests_written: true
  journal_tests_reauthored_executed: true
  presence_only_guard_tests_written: true
  red_baseline_verified: true
red_baseline:
  - test_name: test_harness_exposes_only_the_engine_injected_globals
    file: unit_tests/workflows/test_bp_1100b_4.py
    error: "AssertionError: Lists differ: ['pipeline', 'workflow', 'budget'] != [] (missing engine globals) — Full reachability map: {'agent': True, 'parallel': True, 'pipeline': False, 'phase': True, 'log': True, 'args': True, 'workflow': False, 'budget': False, 'require': True, 'module': True, 'exports': True, 'process': True, '__dirname': True, '__filename': True}"
  - test_name: test_harness_exposes_no_module_loader_to_the_workflow_body
    file: unit_tests/workflows/test_bp_1100b_4.py
    error: "AssertionError: require('fs') did NOT throw inside the harness — the module loader is still reachable from the workflow body."
  - test_name: test_filesystem_dependent_journaling_produces_zero_records_under_the_harness
    file: unit_tests/workflows/test_bp_1100b_4.py
    error: "AssertionError: 1 != 0 : Expected ZERO journal records under the engine-faithful harness ... Found 1 record(s)"
  - test_name: test_one_journal_record_is_appended_per_completed_step
    file: unit_tests/workflows/test_bo_1000c_1a.py
    error: "AssertionError: Items in the second set but not the first: '2' '1' '0' — journal has record groups for [] but the run actually dispatched steps ['0', '1', '2']"
  - test_name: test_journal_records_appear_in_step_order
    file: unit_tests/workflows/test_bo_1000c_1a.py
    error: "AssertionError: False is not true : No journal file was written at all — cannot verify emission order."
  - test_name: test_journal_records_are_still_present_when_the_run_ends
    file: unit_tests/workflows/test_bo_1000c_1a.py
    error: "AssertionError: False is not true : Journal file does not exist after the run's process terminated."
  - test_name: test_run_that_cannot_append_fails_instead_of_passing
    file: unit_tests/workflows/test_bo_1000c_1a.py
    error: "AssertionError: Items in the second set but not the first: '2' '1' '0' — journal has record groups for [] but the run actually dispatched steps ['0', '1', '2']"
  - test_name: test_renaming_the_journal_helper_leaves_the_tests_green
    file: unit_tests/workflows/test_bo_1000c_1a.py
    error: "AssertionError: Items in the second set but not the first: '2' '1' '0' — after renaming appendJournal, journal record groups [] do not match steps dispatched ['0', '1', '2']"
  - test_name: test_unwaived_substring_presence_assertion_is_reported_with_file_symbol_and_source
    file: unit_tests/commit_guardian/test_bp_1100b_5.py
    error: "AssertionError: 2 != 1 : Hook should exit 1. stderr: /usr/bin/python3: can't open file '.../check_presence_only_assertions.py': [Errno 2] No such file or directory"
  - test_name: test_regex_declaration_presence_assertion_is_also_reported
    file: unit_tests/commit_guardian/test_bp_1100b_5.py
    error: "AssertionError: 2 != 1 : Hook should exit 1. stderr: ModuleNotFoundError-equivalent (script does not exist yet)"
  - test_name: test_report_states_the_unreachable_code_rationale_and_names_the_waiver
    file: unit_tests/commit_guardian/test_bp_1100b_5.py
    error: "AssertionError: 'unreachable code' not found in '' : script does not exist yet"
  - test_name: test_waived_assertion_is_not_reported_and_its_reason_is_listed
    file: unit_tests/commit_guardian/test_bp_1100b_5.py
    error: "AssertionError: 2 != 0 : A waiver with a non-empty reason must suppress the violation. stderr: can't open file '.../check_presence_only_assertions.py'"
  - test_name: test_waiver_with_an_empty_reason_does_not_suppress_the_violation
    file: unit_tests/commit_guardian/test_bp_1100b_5.py
    error: "AssertionError: 2 != 1 (subTest reason='empty' and reason='whitespace-only', both fail): script does not exist yet"
  - test_name: test_presence_assertion_over_an_unscanned_file_is_not_reported
    file: unit_tests/commit_guardian/test_bp_1100b_5.py
    error: "AssertionError: 2 != 0 : script does not exist yet"
  - test_name: test_preexisting_assertions_in_untouched_files_are_not_reported
    file: unit_tests/commit_guardian/test_bp_1100b_5.py
    error: "AssertionError: 2 != 0 : script does not exist yet"
  - test_name: test_new_violation_reported_regardless_of_author_or_source_co_modification
    file: unit_tests/commit_guardian/test_bp_1100b_5.py
    error: "AssertionError: 2 != 1 : script does not exist yet"
  - test_name: test_documentation_marker_assertion_is_not_over_matched
    file: unit_tests/commit_guardian/test_bp_1100b_5.py
    error: "AssertionError: 2 != 1 : script does not exist yet"
  - test_name: test_scanned_source_globs_are_read_from_the_guardian_config
    file: unit_tests/commit_guardian/test_bp_1100b_5.py
    error: "AssertionError: 'finalize-feature.js' not found in \"...can't open file '.../check_presence_only_assertions.py'...\""
  - test_name: test_deployed_hook_runs_and_reports_after_build
    file: unit_tests/commit_guardian/test_bp_1100b_5.py
    error: "AssertionError: False is not true : check_presence_only_assertions.py was not deployed to <tmp>/scripts/commit_guardian/check_presence_only_assertions.py."
Wrote 3 new test files satisfying the ORDERING constraint (harness-fidelity tests come first, calibrated directly against run_workflow_under_e2()) plus executed re-authoring of the confirmed grep-only journal incumbent and the new BP-1100b-5 presence-only-assertion guard's own tests. All 19 new test functions verified genuinely RED via `python -m unittest discover` (12 failures across 11 methods in test_bp_1100b_5.py including 2 subTest failures; 3/3 red in test_bp_1100b_4.py; 5/5 red among the new classes appended to test_bo_1000c_1a.py, with the 10 pre-existing grep-only tests in that file left untouched and still green). The journal tests use a test-local `require`-shadowing technique (a temp copy of finalize-feature.js with `const require = undefined` prepended) so they are meaningfully red TODAY without depending on `_workflow_engine_harness.py` already being hardened — avoiding the exact "hidden prerequisite" phantom-done trap the ticket calls out (a reviewer found finalize-feature.js writes 9 journal records under today's un-sandboxed harness with zero implementation). test_bp_1100b_5.py introduces one new test-only convention, `HOOK_TEST_CONFIG` (a temp JSON file path env var for injecting the `presence_only_assertion_guard` config section), documented in the module docstring for python-coder to implement alongside the existing `HOOK_TEST_DIFF` convention. No AC checkbox/table protocol applied (ticket has no `## Agent Contracts` section — v1 ticket per signoff skill §2c.1).

### 2026-08-18 19:40 — python-coder (status: blocker)
feedback-id: fb_2026-08-18_68029716
completion_manifest:
  harness_engine_fidelity_fixed: true
  presence_only_assertion_guard_implemented: true
  journal_write_mechanism_fixed:
    result: false
    reason: "Architecturally impossible without either (a) an escape-hatch trick that evades this ticket's own engine-fidelity check while remaining equally broken in real production, or (b) breaking 4 pre-existing grep-based tests in test_bo_1000c_1a.py that this phase may not turn red. See full analysis below."
    remediation: "architect-review must decide BO-1000c-1a's actual achievable mechanism (see options below); once decided, test-writer re-authors the 5 blocked tests (and, if a redesign is chosen, the 4 pre-existing grep tests) to match, then python-coder re-runs."

BP-1100b-4 (harness engine-fidelity, AC-5) and BP-1100b-5 (presence-only-assertion
guard, all ACs) are fully implemented and green:
- `unit_tests/_workflow_engine_harness.py`: `run_workflow_under_e2()` now runs the
  target script body inside a Node `vm` context contextified with EXACTLY the
  ADR-030 injected globals (agent/parallel/pipeline/phase/log/args/workflow/budget,
  plus `console` as a documented back-compat exception) — `require`/`module`/
  `exports`/`process`/`__dirname`/`__filename` are all unreachable and throw
  ReferenceError, verified by `unit_tests/workflows/test_bp_1100b_4.py` (3/3 green).
  Re-ran every other harness-dependent test file
  (test_workflow_dual_engine.py, test_bp_300e_parse_agent_json.py,
  test_bp_1100f_4.py, test_bo_2300_pause_resume.py,
  test_finalize_baseline_recovery.py) — all still green; no real workflow script
  besides finalize-feature.js referenced a forbidden identifier.
- `templates/scripts/commit_guardian/check_presence_only_assertions.py` (+
  `_presence_only_scanner.py`, split out to respect the 400-line file-size limit)
  is a new staged-hunks-only hook detecting both the substring form and the
  regex-declaration form, honouring `# presence-only: <reason>` waivers (non-empty
  reason only), scoped via `scanned_source_globs` read from
  `presence_only_assertion_guard` in `commit_guardian.json` (both the config key
  and the `hooks_manifest` entry added — n_location_rule '2'), documented in
  `docs/pre-commit-hooks.md`. All 13 tests in
  `unit_tests/commit_guardian/test_bp_1100b_5.py` pass under
  `AC_ENFORCE_STRICT=1`, including the deployed-layout test (build.py auto-deploys
  the whole `templates/scripts/commit_guardian/` directory via `rglob`, so both new
  files land in `scripts/commit_guardian/` with no separate deploy-manifest edit
  needed).

BLOCKER — the journal-write mechanism (5 of test-writer's red_baseline tests:
`test_one_journal_record_is_appended_per_completed_step`,
`test_journal_records_appear_in_step_order`,
`test_journal_records_are_still_present_when_the_run_ends`,
`test_run_that_cannot_append_fails_instead_of_passing`,
`test_renaming_the_journal_helper_leaves_the_tests_green`, all in
`unit_tests/workflows/test_bo_1000c_1a.py`) remain RED — confirmed via
`AC_ENFORCE_STRICT=1` (the AC-enforcement xfail-mask would otherwise hide this).
Tried and reverted the "removed journal" branch the AC's own it_requirements
explicitly authorizes ("the assignee decides... a working journal... or a removed
journal"): deleting `appendJournal()`'s call sites in `narrate()`/`outcome()`
immediately flips 4 DIFFERENT, PRE-EXISTING, currently-green tests in the SAME
file to red (`TestProgressLineAppendedToJournalAtMomentItIsEmitted` x2,
`test_ac2_journal_append_call_count_covers_both_narrate_and_outcome`,
`test_ac2_journal_append_not_deferred_to_end_of_workflow`) — those assert the
journal-append mechanism's declaration/call-sites are PRESENT, so removal is a
regression this phase may not introduce ("no test that was passing before
test-writer ran may now be red"). Reverted; `templates/workflows-js/
finalize-feature.js` now carries only documentation comments (no functional
change) recording this finding at both call sites (narrate/outcome) and at the
`appendJournal()`/`journalPath` declaration.

The "make it work" branch is genuinely blocked by ADR-030 / docs/reference/
workflow-authoring-contract.md: the real E2 engine injects ONLY
agent/parallel/pipeline/phase/log/args/workflow/budget into a workflow script's
top-level body — no filesystem primitive, no `require`, no `module` — confirmed
empirically by the new vm-sandboxed harness (require('fs') throws
ReferenceError). `finalize-feature.js` is the ONLY workflow script in the repo
that ever called `require()`. Evaluated and REJECTED two escape hatches that
would make test-writer's specific require-shadowed calibration tests pass while
remaining equally broken against a real vm-sandboxed engine (the exact
phantom-done shape this epic exists to eliminate): `module.require('fs')`
(`module` is on the harness's own forbidden-names list) and dynamic
`import('fs')` (blocked by default in a `vm.Script` context without an explicit
`importModuleDynamically` callback, which the harness does not — and should
not — provide). Did not implement either.

Three options for architect-review, in order of my own preference:
1. **Redesign the journal as an agent()-dispatched write** (a dispatched
   sub-agent has real Bash/Write tool access, unlike the workflow body itself)
   — legitimate under ADR-030, but adds one extra agent dispatch per narrate()/
   outcome() call (~18/run) and requires test-writer to re-author ALL 9
   journal-related tests (the 5 blocked + the 4 pre-existing) against the new
   mechanism, since none of the current tests exercise agent-dispatch-based
   journaling.
2. **Formally deprecate the on-disk journal** in favour of relying on `log()`
   (already called from narrate()/outcome()) plus whatever mechanism the real
   Claude Code engine uses to persist a workflow's `log()` stream — requires
   confirming that mechanism exists and is pollable by the BO-1000c-1b launcher,
   and requires test-writer to replace all 9 journal tests with tests asserting
   the log-based contract instead of a custom on-disk file.
3. **Accept the current best-effort broken state long-term** (log() emission
   works; the custom journal silently no-ops) and have test-writer soften the
   9 assertions to match — the option I like least, since it leaves
   BO-1000c-1a effectively un-implemented while marked `work_status: done`.

Recommend respawning architect-review with this comment as input; once a
direction is chosen, test-writer re-authors the affected tests, then
python-coder re-runs. `unit_tests/_workflow_engine_harness.py` and the new
BP-1100b-5 hook are NOT blocked by this and should not be re-touched by that
follow-up.

### 2026-08-18 19:55 — main-loop (status: ok)
feedback-id: fb_2026-08-19_d90b26a3

**Design decision made by BrainCandy: option 2, in a variant the analysis above did
not have available. Direction is settled; architect-review does not need to re-run
to choose one.**

**Decision: delete the custom journal and redefine `BO-1000c-1a` on the journal the
engine already writes.**

The missing fact above is that the E2 engine writes a journal of its own, per run, at
`<transcriptDir>/journal.jsonl` — this is the file the `Workflow` tool result points at
("Read `<transcriptDir>/journal.jsonl` — it records each agent's actual return value").
It is not hypothetical: this session has been reading it all day, and the epic drive's
own journal at
`.../subagents/workflows/wf_bead9a97-44c/journal.jsonl` was inspected directly.

So `appendJournal()` has been reimplementing, badly and via a `require()` that cannot
work, a facility the platform already provides for free.

**Granularity change, stated explicitly because it is the real cost.** Counting record
types in that live journal gives **68 `started` and 64 `result`** — one pair per agent
dispatch. The engine journal is therefore **per-agent lifecycle, not per-step**. It does
**not** persist `log()` output, so the "rely on `log()` plus whatever persists the log
stream" form of option 2 was correctly unavailable — there is no such stream. What is
available is agent-level `started`/`result`, and that is what the AC is being redefined
onto. Per-`narrate()`/`outcome()` step granularity is being given up deliberately.

**Work this authorises:**

1. Remove `appendJournal()`, its `journalPath` declaration, and its call sites in
   `narrate()` / `outcome()` from `templates/workflows-js/finalize-feature.js`, along
   with the documentation comments the previous pass left recording the finding. The
   AC's own `it_requirements` already authorise "a removed journal".
2. Re-author all **nine** journal tests in `unit_tests/workflows/test_bo_1000c_1a.py`
   against the engine journal — the 5 currently-red ones **and** the 4 pre-existing
   green ones. Those 4 are the blocker described above precisely because they assert the
   mechanism's *call sites are present*; they are presence-only assertions of exactly the
   kind `BP-1100b-5` (shipped green in this same ticket) exists to ban. They should not be
   preserved — they are the defect, not a constraint on the fix. Deleting them is not the
   "no test that was passing may now be red" violation the previous pass reasonably feared,
   because this comment is the authorisation it was waiting for.
3. Leave `unit_tests/_workflow_engine_harness.py` and the `BP-1100b-5` hook untouched, as
   the previous pass asked — both are green and out of scope for this follow-up.

**Rejected, and why, so this is not relitigated:** the agent()-dispatched write keeps
per-step granularity but costs roughly 18 extra agent dispatches per finalize run, which
is a large latency and token cost to pay for progress logging. Accepting the silent no-op
and softening the assertions was rejected outright: it would leave `BO-1000c-1a`
unimplemented while marked done, which is the phantom-done pattern this epic exists to
remove.

### 2026-08-18 21:10 — python-coder (status: ok)
feedback-id: fb_2026-08-19_4514b454

Decision above implemented. `appendJournal()`, `journalPath`, both call sites and the
stale finding-comments are gone from `templates/workflows-js/finalize-feature.js`;
`log()` in `narrate()`/`outcome()` is untouched. The file no longer calls `require(`
anywhere — it was the only workflow script in the repo that ever did — and
`node --check` passes.

**Deviation from the "nine tests" figure, reported rather than glossed.** The decision
named 4 pre-existing green tests as the blocker, because those are the ones that flip red
when only the *call sites* are removed. Full removal takes the declaration and
`journalPath` too, which makes **all 10** presence-only tests across the first four
classes vacuous, not 4 — every one of them greps for text that no longer exists anywhere
in the source. All 10 were deleted on the same rationale the decision gave for the 4 it
named. Final count is **5** tests, not 9.

**Honest limitation.** The engine writes `journal.jsonl` itself, and the harness's Node
stub has no engine-internal journal writer, so no unit test can read back a real
engine-produced journal — that needs an integration harness around E2 that does not
exist. Four of the five tests execute the real `finalize-feature.js` through
`run_workflow_under_e2()` and assert on `AgentCall` dispatch data, which is the same
per-dispatch signal the engine journal is keyed on, observed from the harness side. This
is stated in the module docstring rather than left implied.

The fifth is a source-text assertion, and deliberately so: it is an **absence** guard
(`assertNotIn` on `require(`, `appendJournal`, `journalPath`), not a presence claim. It
fails the moment the dead mechanism reappears. Confirmed it discriminates by checking all
three tokens were present in the pre-fix committed file.

Self-checked all five against `check_presence_only_assertions.py` — the very hook this
ticket ships — using the real `commit_guardian.json` config: exit 0, zero violations.

**Verified:** `test_bo_1000c_1a.py` 5 passed under `AC_ENFORCE_STRICT=1`;
`unit_tests/workflows/` + `test_bp_1100b_5.py` together 413 passed, 12 subtests, no
regressions; `ruff check` clean; `node --check` clean.

`BO-1000c-1a.yaml` amended in the same pass — `criteria`, `test_spec` and the
`delivers_to` contract rewritten, `covered_by` populated, and an `amended_by` entry
recording that this is a requirement change rather than a clarification, including the
downstream impact on `BO-1000c-1b` / `BO-1000c-2` / `BO-1000c-2-i`, which consume the old
contract and must be re-read before they are built.

`architect-review` set to `not_needed`: it was on the map to choose between the three
options, and BrainCandy chose directly.
