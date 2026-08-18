---
title: "Build manifest records every managed template and every deployed output, so the drift gates have something to compare"
status: todo
components:
  - build_pipeline
created: 2026-08-17
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
source_ac: BP-100k-1
ac_coverage:
  - BP-100k-1
  - BP-100k-2
ac_traceability:
  l2:
    - BP-100k-1
    - BP-100k-2
  l3: []
  ac_path: docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/
change_target: pipeline
risk_surface: contract_boundary
complexity: medium
roadmap_phase: phase_1
advances_current_outcome: true
documentation_required: true
files_touched:
  - scripts/build_helpers.py
  - unit_tests/build_guards/test_bp_100k_1.py
  - unit_tests/build_guards/test_bp_100k_2.py
agents:
  architect-review: signed_off
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

# 07: The manifest records what the drift gates compare against

## Actor / Goal

As the build-drift and output-drift gates, I want the build manifest to record a
comparable fingerprint for **every** template artifact the build manages and a source
mapping for **every** deployed output it writes — not just the agent-template family —
so that inspecting an artifact yields a match/drift verdict instead of an
"absent from the manifest" notice that reads as a clean run.

## Remediation Context (scope refresh 2026-08-17)

**A gate with an empty reference set.** `write_build_manifest()` in
`scripts/build_helpers.py` records template fingerprints for `templates/agents/*.md`
only, and its `output_mappings` section does not cover every deployed output. For every
other artifact the gates announce "not in the manifest" — and then exit clean. Drift in
a commit-guardian hook script, or a hand-edit to a deployed agent definition, can
therefore *never* be detected, while the gate reports success.

This is the same failure shape as ticket 03 (`BP-100i-3`): a check that cannot compare
what it inspected, reporting the run as passing. The two ACs here are the **write side**
of that fix. Ticket 08 is the read side and depends on this ticket landing first.

**Do: derive the recorded set from the real copy set, don't add a second list.** Both
ACs explicitly forbid a parallel hardcoded inventory that can drift from the one the
build actually uses — adding a new template family or deploy phase must extend manifest
coverage automatically, or fail the build.

## AC References

Resolves **BP-100k-1** and **BP-100k-2** (verbatim Gherkin in
`docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/`). The YAML is the
source of truth; the Gherkin below is for review comprehension.

### BP-100k-1 — template fingerprints

```gherkin
Given the build has just run over an unmodified checkout and written its build manifest,
And a template artifact that the build copies into the package's shipped surface is
  staged for commit — including template families other than the agent templates,
  for example a commit-guardian hook script,
When the template-drift gate inspects that staged artifact and looks it up in the manifest,
Then the manifest yields a recorded fingerprint for that artifact,
And the gate reports, for that artifact, either that it matches the recorded fingerprint
  or that it has drifted from it,
And the gate does not report that artifact as absent from the manifest.
```

### BP-100k-2 — output mappings

```gherkin
Given the build has just run over an unmodified checkout and deployed its outputs,
And a deployed output the build produced is staged for commit — for example a deployed
  agent definition in the deployed agents directory,
When the output-drift gate inspects that staged output and looks up which source it was
  produced from,
Then the manifest's output-mapping record names that deployed output and the source
  artifact it was produced from,
And the gate reports, for that output, either that it matches its recorded source or
  that it has drifted from it,
And the gate does not report that output as absent from the output mapping.
```

- [ ] AC-1: after a real build, the manifest yields a fingerprint for a non-agent template family (BP-100k-1)
- [ ] AC-2: the executed template-drift gate emits match-then-drift for that template, never absent-from-manifest (BP-100k-1)
- [ ] AC-3: manifest template coverage equals the build's actual copy set (BP-100k-1)
- [ ] AC-4: the output mapping resolves a deployed output to the source it was produced from (BP-100k-2)
- [ ] AC-5: the executed output-drift gate emits match-then-drift for that output, never unregistered (BP-100k-2)
- [ ] AC-6: output-mapping coverage equals the set of files the deploy phases actually wrote (BP-100k-2)

## Test Requirements

```yaml
tests:
  - name: test_manifest_records_a_fingerprint_for_a_non_agent_template_family
    file: unit_tests/build_guards/test_bp_100k_1.py
    covers: [BP-100k-1]
    framework: unittest
    type: behavioral
    asserts: After the build runs over an unmodified checkout, the written build manifest yields a recorded fingerprint for a commit-guardian hook template (a family other than templates/agents/*.md), looked up by its repo-relative template path.
  - name: test_drift_gate_emits_match_then_drift_for_that_template
    file: unit_tests/build_guards/test_bp_100k_1.py
    covers: [BP-100k-1]
    framework: unittest
    type: behavioral
    asserts: Executing check_build_drift.py as a process against that staged non-agent template yields a match verdict on an unmodified copy and a drift verdict once the staged copy is mutated — the gate is run, not read.
  - name: test_gate_never_reports_a_managed_template_as_absent_from_manifest
    file: unit_tests/build_guards/test_bp_100k_1.py
    covers: [BP-100k-1]
    framework: unittest
    type: behavioral
    asserts: The executed gate's output for that staged template contains no absent-from-manifest notice; the not-in-manifest branch is not taken for any template family the build copies.
  - name: test_manifest_coverage_equals_the_build_copy_set
    file: unit_tests/build_guards/test_bp_100k_1.py
    covers: [BP-100k-1]
    framework: unittest
    type: behavioral
    asserts: The manifest's recorded template key set, after a real build, equals the set of template paths the build actually copies into the shipped surface — count-agnostic, so a newly added template family cannot silently escape coverage.
  - name: test_output_mapping_names_the_deployed_output_and_its_source
    file: unit_tests/build_guards/test_bp_100k_2.py
    covers: [BP-100k-2]
    framework: unittest
    type: behavioral
    asserts: After the build runs and deploys, the manifest's output-mapping section resolves a deployed agent definition under the deployed agents directory to the source artifact it was produced from.
  - name: test_output_drift_gate_emits_match_then_drift_for_that_output
    file: unit_tests/build_guards/test_bp_100k_2.py
    covers: [BP-100k-2]
    framework: unittest
    type: behavioral
    asserts: Executing check_output_drift.py as a process against that staged deployed output yields a match verdict on an untouched copy and a drift verdict after the deployed copy is hand-edited — the gate is run, not read.
  - name: test_gate_never_reports_a_build_produced_output_as_unregistered
    file: unit_tests/build_guards/test_bp_100k_2.py
    covers: [BP-100k-2]
    framework: unittest
    type: behavioral
    asserts: The executed gate's output for a build-produced deployed file contains no not-in-output_mappings notice; the unregistered branch is not taken for any output the build actually produces.
  - name: test_output_mapping_covers_every_deploy_phase_output
    file: unit_tests/build_guards/test_bp_100k_2.py
    covers: [BP-100k-2]
    framework: unittest
    type: behavioral
    asserts: The set of paths recorded in output_mappings after a real build equals the set of files the deploy phases actually wrote — count- and phase-agnostic, so a phase that writes an output without registering a mapping is detected rather than tolerated.
```

## Implementation Notes

```yaml
reference_file_path: scripts/build_helpers.py
n_location_rule: '1'
post_write_commands:
  - python scripts/build.py --target-dir .
required_skills:
  - python-coder
constraints:
  - The manifest writer currently records fingerprints for the agent-template family only;
    the recorded set must be derived from the same template inventory the build actually
    copies, not from a second hardcoded list that can drift from it.
  - Output-mapping entries must be recorded by the deploy phases as they write each output,
    so a newly added output is registered by the act of deploying it and cannot be forgotten
    in a separate bookkeeping step.
  - 'Coverage must be derived, not enumerated by hand: adding a new template family or a new
    deploy phase must extend manifest coverage without a separate edit, or the omission must
    fail the build.'
  - Verify behaviorally — run the build, then execute the drift gates as processes against a
    real artifact currently reported as unregistered, and assert they now yield a match/drift
    verdict. Do NOT grep the manifest writer's source; a presence-only assertion here would be
    the exact defect ticket 09 (BP-1100b-5) exists to reject.
  - 'Must follow the repo error-handling policy: specific-exception try/except around file and
    JSON I/O, log at WARNING or higher or re-raise; no bare or silent excepts.'
  - 'Bundle A1 (shared reviewable diff): BP-100k-1 and BP-100k-2 both edit
    scripts/build_helpers.py::write_build_manifest(). They land as ONE diff. No other ticket
    in this epic may edit scripts/build_helpers.py concurrently — see Master_Plan parallelism.'
```

## Out of Scope

- The gates' *reporting* behaviour for artifacts that remain uncomparable — that is
  ticket 08 (BP-100k-3 / -3-i), which depends on this ticket.
- `BP-017` (symlink shim target relativity) also edits `scripts/build_helpers.py`. It is
  **not** in this epic; if it is ever pulled in, sequence it after this ticket.

## Risk & Safety

- Touches money? No.
- Touches data? No. Manifest content only; no schema, no user data.
- Reversibility? Fully — manifest is regenerated by `build.py` on every run.
- Blast radius: widening manifest coverage will make the drift gates start reporting on
  artifacts they previously skipped. Expect previously-invisible genuine drift to surface
  on first run; triage it inside this ticket rather than narrowing coverage to keep the
  gate quiet.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| BP-100k-1 | | | |
| BP-100k-2 | | | |

## Sign-offs

- [x] architect-review — 2026-08-18 14:00
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

### 2026-08-18 14:00 — architect-review (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  blast_radius_analyzed: true
  rubric_criteria_evaluated: true
  small_large_classification: true
Classified small: 3 touched files (scripts/build_helpers.py + 2 new test files), single component (build_pipeline), no cross-module boundary crossed, and no always-large trigger fired (no Alembic migration, no hypertable change, no FastAPI surface change, no ADR-contract file touched — confirmed no ADR references build_manifest/output_mappings). No research-agent/Agent tool was available in this invocation's toolset, so blast-radius analysis was performed directly via Read/grep against write_build_manifest(), _compute_output_mappings(), and the two drift-gate scripts (check_build_drift.py, check_output_drift.py) rather than by spawning research-agent — noting this as a process deviation for the record. requires_adr and requires_diagram remain false as already set in frontmatter.
