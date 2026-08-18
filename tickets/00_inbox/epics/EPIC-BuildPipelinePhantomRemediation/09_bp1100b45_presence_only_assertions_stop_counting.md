---
title: "Presence-only assertions stop counting as coverage: re-author the journal test, then gate the shape"
status: todo
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
  - templates/scripts/commit_guardian/commit_guardian.json
  - docs/pre-commit-hooks.md
  - unit_tests/_workflow_engine_harness.py
  - unit_tests/workflows/test_bo_1000c_1a.py
  - templates/workflows-js/finalize-feature.js
  - unit_tests/commit_guardian/test_bp_1100b_5.py
  - unit_tests/workflows/test_bp_1100b_4.py
agents:
  architect-review: needed
  test-writer: needed
  python-coder: needed
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
- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] ac-validator
- [ ] ac-fulfillment-gate
- [ ] commit
- [ ] pull-request

## Comments
