---
title: "Drift gates report an uncomparable artifact as a gap or a declared exemption, never as a clean pass"
status: todo
components:
  - build_pipeline
created: 2026-08-17
depends_on:
  - 07_bp100k12_manifest_records_what_the_gates_compare.md
priority: high
requires_diagram: false
requires_adr: false
source_ac: BP-100k-3
ac_coverage:
  - BP-100k-3
  - BP-100k-3-i
ac_traceability:
  l2:
    - BP-100k-3
  l3:
    - BP-100k-3-i
  ac_path: docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/
change_target: pipeline
risk_surface: contract_boundary
complexity: medium
roadmap_phase: phase_1
advances_current_outcome: true
documentation_required: true
files_touched:
  - templates/scripts/commit_guardian/check_build_drift.py
  - templates/scripts/commit_guardian/check_output_drift.py
  - templates/scripts/commit_guardian/commit_guardian.json
  - unit_tests/commit_guardian/test_bp_100k_3.py
  - unit_tests/commit_guardian/test_bp_100k_3_i.py
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

# 08: "Could not compare" stops reading as "compared and matched"

## Actor / Goal

As a developer trusting the drift gates, I want an artifact the gate could not compare
to be reported as a **coverage gap** (or as a **declared exemption** with a stated
ground) and counted in the run summary — never folded into the verified population and
never allowed to exit as if the run were clean — so that a passing gate means the
artifacts were actually checked.

## Remediation Context (scope refresh 2026-08-17)

**The INFO-downgrade pattern, one directory over.** This is the generic form of the
defect ticket 03 fixes in `check_hook_parity.py`: the gate emits an informational line
for an artifact it cannot compare and then exits clean. A reader — and CI — sees a pass.

Ticket 07 closes the manifest gaps that make comparison impossible. This ticket fixes
what the gates *say and return* about anything still uncomparable after that. Both
halves are required: fixing only the manifest leaves the silent-pass branch in place for
the next unregistered artifact; fixing only the reporting turns every currently-invisible
gap into a hard block.

**The paired L3 is the anti-overcorrection guard.** `BP-100k-3-i` requires that a
freshly built, unmodified tree yields a zero uncomparable count and a clean exit — it
fails both if manifest coverage is still incomplete *and* if the stricter reporting
over-fires. It cannot be separated from its parent.

## AC References

Resolves **BP-100k-3** (L2) and **BP-100k-3-i** (L3). Verbatim Gherkin in
`docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/`; the YAML is the
source of truth.

### BP-100k-3 — gap vs exemption vs pass

```gherkin
Given an artifact that sits inside a directory the drift gates inspect but that the
  build deliberately does not manage — a hand-maintained file with no build-produced
  counterpart,
When a drift gate inspects that artifact,
Then the gate reports it as a declared exemption and names the ground on which it is exempt,
And given a second artifact that is neither recorded in the build manifest nor declared exempt,
When the same gate inspects it,
Then the gate reports it as a coverage gap naming the artifact and the action that would
  register it,
And the gate's run summary states a non-zero count of artifacts it could not compare and
  does not describe that run as clean,
And an artifact the gate could not compare is never counted among the artifacts it verified
  — "could not compare" and "compared and matched" are distinguishable in the gate's output
  and in its exit status.
```

### BP-100k-3-i — no false alarm on a clean tree

```gherkin
Given a checkout in which the build has just run and no file has been modified since,
When both drift gates run over the full set of artifacts they inspect,
Then the count of artifacts reported as neither recorded nor declared exempt is zero,
And no artifact is reported as drifted,
And each gate reports the run as clean and exits zero,
And the stricter reporting introduced for uncomparable artifacts produces no failure on a
  tree that matches exactly what the build just produced.
```

- [ ] AC-1: a declared-exempt artifact is reported as exempt and its ground is named (BP-100k-3)
- [ ] AC-2: an unrecorded, undeclared artifact is reported as a coverage gap with the registering action (BP-100k-3)
- [ ] AC-3: the run summary carries a non-zero uncomparable count and is not described as clean (BP-100k-3)
- [ ] AC-4: uncomparable is distinguishable from compared in both output and exit status (BP-100k-3)
- [ ] AC-5: both gates honour the same exemption registry; a groundless entry is rejected (BP-100k-3)
- [ ] AC-6: a freshly built tree yields zero uncomparable, no drift, clean verdict, exit zero (BP-100k-3-i)

## Test Requirements

```yaml
tests:
  - name: test_declared_exemption_is_reported_as_exempt_and_names_its_ground
    file: unit_tests/commit_guardian/test_bp_100k_3.py
    covers: [BP-100k-3]
    framework: unittest
    type: behavioral
    asserts: Running each drift gate as a process over a synthesized tree containing one declared-exempt hand-maintained artifact reports that artifact as a declared exemption and includes the stated ground in the output.
  - name: test_unrecorded_undeclared_artifact_is_reported_as_a_coverage_gap
    file: unit_tests/commit_guardian/test_bp_100k_3.py
    covers: [BP-100k-3]
    framework: unittest
    type: behavioral
    asserts: The same executed run reports a second artifact that is neither in the manifest nor declared exempt as a coverage gap, naming the artifact and the action that would register it.
  - name: test_run_summary_counts_uncomparable_artifacts_and_is_not_called_clean
    file: unit_tests/commit_guardian/test_bp_100k_3.py
    covers: [BP-100k-3]
    framework: unittest
    type: behavioral
    asserts: The executed gate's run summary states a non-zero count of artifacts it could not compare and does not describe that run as clean.
  - name: test_uncomparable_is_distinguishable_from_compared_in_output_and_exit_status
    file: unit_tests/commit_guardian/test_bp_100k_3.py
    covers: [BP-100k-3]
    framework: unittest
    type: behavioral
    asserts: An artifact the gate could not compare is absent from the verified count, and the process exit status of a run containing an uncomparable artifact differs from that of a run in which every artifact was compared and matched.
  - name: test_both_gates_honour_the_same_exemption_registry
    file: unit_tests/commit_guardian/test_bp_100k_3.py
    covers: [BP-100k-3]
    framework: unittest
    type: behavioral
    asserts: check_build_drift.py and check_output_drift.py, each executed as a process against the same declared exemption, both report it as exempt — neither ignores a declaration the other honours.
  - name: test_exemption_entry_without_a_ground_is_rejected
    file: unit_tests/commit_guardian/test_bp_100k_3.py
    covers: [BP-100k-3]
    framework: unittest
    type: behavioral
    asserts: An exemption entry carrying no stated ground causes the executed gate to reject the registry entry rather than silently suppressing the artifact.
  - name: test_freshly_built_tree_yields_zero_uncomparable_artifacts
    file: unit_tests/commit_guardian/test_bp_100k_3_i.py
    covers: [BP-100k-3-i]
    framework: unittest
    type: behavioral
    asserts: After running the real build over an unmodified checkout, each drift gate executed as a process over its full inspection set reports an uncomparable count of exactly zero — read from the gate's own summary, not from an allowlist of expected names.
  - name: test_freshly_built_tree_reports_no_drifted_artifact
    file: unit_tests/commit_guardian/test_bp_100k_3_i.py
    covers: [BP-100k-3-i]
    framework: unittest
    type: behavioral
    asserts: The same executed runs report no artifact as drifted on a tree in which no file has been modified since the build.
  - name: test_both_gates_report_clean_and_exit_zero_on_a_freshly_built_tree
    file: unit_tests/commit_guardian/test_bp_100k_3_i.py
    covers: [BP-100k-3-i]
    framework: unittest
    type: behavioral
    asserts: check_build_drift.py and check_output_drift.py each describe the run as clean and terminate with exit status zero on the freshly built tree.
  - name: test_stricter_uncomparable_reporting_raises_no_false_alarm_on_the_real_tree
    file: unit_tests/commit_guardian/test_bp_100k_3_i.py
    covers: [BP-100k-3-i]
    framework: unittest
    type: behavioral
    asserts: The stricter uncomparable-artifact reporting introduced by BP-100k-3 produces no failure when the gates are run over the full real tree the build just produced — the deployed hook copies under scripts/commit_guardian/, not only the templates/ source.
```

## Implementation Notes

```yaml
reference_file_path: templates/scripts/commit_guardian/check_build_drift.py
n_location_rule: all
post_write_commands:
  - python scripts/build.py --target-dir .
required_skills:
  - python-coder
config_schema_fragment:
  drift_gate_exemption_registry:
    type: object
    description: Declared list of artifacts the drift gates deliberately do not police, each
      with a stated ground, so an intentional exemption is distinguishable from an accidental
      omission from the build manifest.
constraints:
  - 'REGISTRATION SURFACE: the exemption-registry key belongs in
    templates/scripts/commit_guardian/commit_guardian.json — the authoritative guardian config
    that also holds hooks_manifest. There is NO config/commit_guardian.json in this repo, and
    templates/commit-guardian/commit_guardian.json is a different, much smaller file that is
    NOT the registration surface. Registering the key in the wrong file yields an inert
    declaration that neither gate reads.'
  - 'SERIALIZATION: templates/scripts/commit_guardian/commit_guardian.json is also edited by
    ticket 09 (BP-1100b-5). These two tickets MUST NOT run concurrently — the supervisor
    serializes them, and whichever lands second rebases onto the first rather than
    overwriting the config.'
  - Both drift gates must consume the same exemption declaration; a declaration honoured by
    one gate and ignored by its sibling reintroduces the ambiguity this AC removes.
  - The "could not compare" population must be surfaced in the run summary as a count, not
    only as per-artifact informational lines that a reader skims past.
  - Exit status must distinguish a clean run from a run that skipped artifacts; a run that
    compared nothing must not exit as if it had compared everything.
  - An exemption entry without a stated ground must itself be rejected, so the registry cannot
    become a silent suppression list.
  - Exercise the gates from their DEPLOYED copies under scripts/commit_guardian/ after
    build.py, not only from the templates/ source tree — a template-only edit leaves the
    running hook unchanged.
  - The zero-uncomparable assertion must be count-based over the gate's own summary, not an
    allowlist of expected artifact names; an assertion enumerating today's artifacts would
    pass while a newly added output silently escapes coverage.
  - Verify behaviorally — execute each gate against a synthesized tree containing one exempt
    artifact and one unrecorded, undeclared artifact, and assert the two are reported
    differently and that the summary counts the uncompared one. Do NOT grep the gate source.
  - 'Must follow the repo error-handling policy: specific-exception try/except around file and
    JSON I/O, log at WARNING or higher or re-raise; no bare or silent excepts.'
```

## Out of Scope

- Manifest coverage itself — ticket 07, which this ticket depends on.
- `check_hook_parity.py`'s missing-script branch — ticket 03. Same pattern, different
  file; the two should land the same "no silent INFO pass" convention.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Yes — gate logic and a config key; revert restores current behaviour.
- Blast radius: **these gates run at pre-commit time.** A stricter exit status can block
  commits repo-wide. `BP-100k-3-i` is the guard against that and must be green on the
  real freshly-built tree before this ticket signs off — not on a synthesized subset.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| BP-100k-3 | | | |
| BP-100k-3-i | | | |

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
