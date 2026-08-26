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
- [x] test-writer — 2026-08-19 16:39
- [x] python-coder — 2026-08-25 12:50
- [ ] test-runner
- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] ac-validator
- [ ] ac-fulfillment-gate
- [ ] commit
- [ ] pull-request

## Comments

### 2026-08-19 16:39 — test-writer (status: ok)
feedback-id: fb_2026-08-19_99eeef65
completion_manifest:
  test_bp_100k_3_written: true
  test_bp_100k_3_i_written: true
  red_baseline_captured: true
  scope_limited_to_test_files: true

## Test Writer — Completion Report

### Tests Written
| File | Directory | Framework | Status |
|---|---|---|---|
| test_bp_100k_3.py | unit_tests/commit_guardian/ | unittest (behavioral, subprocess) | written (6 tests, all RED) |
| test_bp_100k_3_i.py | unit_tests/commit_guardian/ | unittest (behavioral, subprocess) | written (4 tests, 3 already green, 1 RED) |

All 10 tests execute the real, unmodified gate modules (check_build_drift.py /
check_output_drift.py) as subprocesses against synthesized or real deployed
layouts — never a grep of the gate source. test_bp_100k_3.py additionally
defines the OUTPUT + EXIT-CODE CONTRACT (UNCOMPARABLE:/RESULT/REJECTED
EXEMPTION ENTRY markers, exit codes 0/1/2) this ticket's implementation must
satisfy — documented in the module docstring for python-coder.

### Verification Run
- Command: `AC_ENFORCE_STRICT=1 python3 -m pytest unit_tests/commit_guardian/test_bp_100k_3.py unit_tests/commit_guardian/test_bp_100k_3_i.py -v`
- test_bp_100k_3.py: **RED** — 5 of 6 top-level tests FAILED outright; the 6th
  (`test_exemption_entry_without_a_ground_is_rejected`) shows as PASSED at the
  top-level line (a pytest/unittest subTest display quirk with no plugin
  installed) but all 3 of its `subTest` cases FAILED (SUBFAILED in the
  summary) — file exit code 1. Every failure is the expected `AssertionError`
  (UNCOMPARABLE:/RESULT/REJECTED EXEMPTION ENTRY markers absent) against the
  current, unmodified gates, which today only print a bare INFO line and
  always exit 0 for an unregistered artifact.
- test_bp_100k_3_i.py: **3 of 4 tests PASS today; 1 is RED.** This matches
  the ticket's own expectation ("BP-100k-3-i's three tests may already
  pass") — confirmed, not forced. The 3 passing tests
  (`test_freshly_built_tree_yields_zero_uncomparable_artifacts`,
  `test_freshly_built_tree_reports_no_drifted_artifact`,
  `test_stricter_uncomparable_reporting_raises_no_false_alarm_on_the_real_tree`)
  are count/marker-based against the REAL, freshly-rebuilt worktree and
  legitimately hold today because ticket 07 (a78700a9) already closed
  manifest coverage — no "not in manifest"/"BLOCKED" lines exist on this
  real tree, and no import/manifest-resolution errors occur from the
  deployed hook copies. `test_both_gates_report_clean_and_exit_zero_on_a_freshly_built_tree`
  is RED because it requires the new aggregate "RESULT verified=<N>
  uncomparable=<M> drifted=<D>" summary line, which does not exist yet.
  Overall file exit code: 1 (red).

### Notes
- Setup for test_bp_100k_3_i.py runs the REAL self-build
  (`python scripts/build.py --target-dir <this worktree root>`) to establish
  "the build has just run and no file has been modified since" as a literal
  fact, mirroring the precedent already established in
  `test_bp_1100b_5.py::TestDeployedHookRunsAndReportsAfterBuild`. This
  refreshes this worktree's own gitignored build artifacts
  (`.build_manifest.json`, `scripts/commit_guardian/*`, `.claude/*`,
  `.agents/rules/*`) in place. It ALSO regenerated 6 tracked
  `docs/agents/cards/*.card.md` self-description files (reflecting AC-store
  renumbering — e.g. GE-119c → GE-120c — unrelated to this ticket); I
  reverted those via `git restore` so this sign-off's working tree contains
  only the two new test files. `git status --short` confirms: only
  `unit_tests/commit_guardian/test_bp_100k_3.py` and
  `unit_tests/commit_guardian/test_bp_100k_3_i.py` are new/untracked; no
  tracked file has a diff. (An unrelated pre-existing untracked changelog
  entry dated 2026-08-18 predates this session and was not touched.)
- No `## Agent Contracts` section is present in this ticket body (v1
  format) — the AC-aware / AC Coverage table-fill behavior does not apply
  per the v1 Fallback rule; the table was left untouched for a later agent
  per the standard column-ownership convention.
- No `## Implementation Tasks` section exists on this ticket, so §1.5 of the
  signoff skill had nothing to flip.

red_baseline:
  - test_name: test_declared_exemption_is_reported_as_exempt_and_names_its_ground
    file: unit_tests/commit_guardian/test_bp_100k_3.py
    error: "AssertionError: 'UNCOMPARABLE: EXEMPT leafcutter-ai/templates/agents/exempt_hand_maintained.md' not found in 'check-build-drift: INFO — leafcutter-ai/templates/agents/exempt_hand_maintained.md not in manifest (new template — run build.py before committing built outputs).\\ncheck-build-drift: INFO — leafcutter-ai/templates/agents/orphan_new_template.md not in manifest (new template — run build.py before committing built outputs).\\n'"
  - test_name: test_unrecorded_undeclared_artifact_is_reported_as_a_coverage_gap
    file: unit_tests/commit_guardian/test_bp_100k_3.py
    error: "AssertionError: 'UNCOMPARABLE: GAP leafcutter-ai/templates/agents/orphan_new_template.md' not found in the same INFO-only output"
  - test_name: test_run_summary_counts_uncomparable_artifacts_and_is_not_called_clean
    file: unit_tests/commit_guardian/test_bp_100k_3.py
    error: "AssertionError: unexpectedly None : No RESULT summary line found (expected 'check-build-drift: RESULT verified=<N> uncomparable=<M> drifted=<D>')"
  - test_name: test_uncomparable_is_distinguishable_from_compared_in_output_and_exit_status
    file: unit_tests/commit_guardian/test_bp_100k_3.py
    error: "AssertionError: unexpectedly None : No RESULT summary line in the uncomparable run"
  - test_name: test_both_gates_honour_the_same_exemption_registry
    file: unit_tests/commit_guardian/test_bp_100k_3.py
    error: "AssertionError: 'UNCOMPARABLE: EXEMPT leafcutter-ai/templates/agents/exempt_shared.md' not found in 'check-build-drift: INFO — leafcutter-ai/templates/agents/exempt_shared.md not in manifest (new template — run build.py before committing built outputs).\\n'"
  - test_name: test_exemption_entry_without_a_ground_is_rejected (subTest case='missing ground key')
    file: unit_tests/commit_guardian/test_bp_100k_3.py
    error: "AssertionError: 'REJECTED EXEMPTION ENTRY: leafcutter-ai/templates/agents/would_be_exempt.md' not found in 'check-build-drift: INFO — ... not in manifest ...'"
  - test_name: test_exemption_entry_without_a_ground_is_rejected (subTest case='empty-string ground')
    file: unit_tests/commit_guardian/test_bp_100k_3.py
    error: "AssertionError: 'REJECTED EXEMPTION ENTRY: leafcutter-ai/templates/agents/would_be_exempt.md' not found in 'check-build-drift: INFO — ... not in manifest ...'"
  - test_name: test_exemption_entry_without_a_ground_is_rejected (subTest case='whitespace-only ground')
    file: unit_tests/commit_guardian/test_bp_100k_3.py
    error: "AssertionError: 'REJECTED EXEMPTION ENTRY: leafcutter-ai/templates/agents/would_be_exempt.md' not found in 'check-build-drift: INFO — ... not in manifest ...'"
  - test_name: test_both_gates_report_clean_and_exit_zero_on_a_freshly_built_tree
    file: unit_tests/commit_guardian/test_bp_100k_3_i.py
    error: "AssertionError: unexpectedly None : No RESULT summary line found for check-build-drift (expected 'check-build-drift: RESULT verified=<N> uncomparable=<M> drifted=<D>')"
    note: "the other 3 tests in this file (test_freshly_built_tree_yields_zero_uncomparable_artifacts, test_freshly_built_tree_reports_no_drifted_artifact, test_stricter_uncomparable_reporting_raises_no_false_alarm_on_the_real_tree) already PASS against the unmodified gates on the real, freshly-rebuilt worktree — legitimate per the ticket's own anti-overcorrection framing (ticket 07 already closed manifest coverage), not forced or under-specified."

### 2026-08-25 12:50 — python-coder (status: ok)
feedback-id: fb_2026-08-25_ebacd045
completion_manifest:
  check_output_drift_and_main_unified: true
  regression_test_added: true
  all_red_baseline_tests_green: true
  coordinator_delegation_fix_independently_verified: true

## Python-Coder — Completion Report

Unified the two contracts in `check_output_drift.py`: `check_output_drift()` is now
the single scan+report+verdict implementation (tri-state 0/1/2, RESULT line, gap
detection, `verified==0` floor); `main()` resolves the manifest and derives
`output_dirs`, then delegates via `return check_output_drift(output_dirs=...,
manifest_path=..., repo_root=...)`. Added `TestFunctionAndMainAgreeOnAnUnrecordedArtifact`
to `unit_tests/commit_guardian/test_bp_100k_3.py` (3 tests) proving the function
(imported directly) and `main()` (subprocess) agree on a tree with one recorded and
one unrecorded output: both signal non-zero, both emit `UNCOMPARABLE: GAP` and the
`RESULT` line, and both reach the identical tri-state verdict. All 9 tests in that
file pass (`AC_ENFORCE_STRICT=1`); `test_bp_100k_3_i.py` (4/4), the three direct-caller
tests in `test_bp100_drift_docs_compile.py`, and `tests/test_build_artifact_parity.py`
(6 passed, 28 subtests) all pass. `ruff check` on both files touched: clean.

**Finding for the next reader — a delegation-invariant regression I introduced and did
not catch myself:** my first pass at this unification kept an early `if output_mappings
is None: return 0` in `main()` BEFORE the call to `check_output_drift()`. At HEAD, `main()`
already delegated to `check_output_drift()` for its scan; my added early-return sat in
front of that delegation and could short-circuit before it was ever reached whenever
`_load_output_mappings` returned `None` for a resolved-but-unreadable/malformed manifest.
`tests/test_build_artifact_parity.py::TestOutputDriftCoversAllShimmedDirs` — a file outside
my edit scope — went from green at HEAD to red under my change; it monkeypatches
`module.check_output_drift` and asserts `main()` actually reaches it. I misread the RED
result as a pre-existing, unrelated fixture bug ("the fake manifest path doesn't exist on
disk") and reported it as such — that diagnosis was wrong, and acting on it would have
left the delegation gap in place while the test's fixture was blamed instead. The
coordinator correctly identified the regression, replaced the early return with
`output_mappings = _load_output_mappings(manifest_path) or {}` (best-effort — `main()`'s
job is to always hand a directory list to `check_output_drift()`, which owns the
manifest-absent warning and the verdict) and separately corrected two stale expectations
in that same test file (`repo_root = manifest_path.parent`, not `.parent.parent`; the
`.agents/rules` category moved to a manifest-derived list rather than a hardcoded shim
path — both artifacts of the BP-100k-2 fix that test hadn't caught up to). I re-read
`main()`/`check_output_drift()` as they now stand, traced the fake-resolve test scenario
by hand against the current code, re-ran the full `test_bp_100k_3*` / `test_bp100_drift_docs_compile.py`
/ `test_build_artifact_parity.py` suites (all green) plus a broader sweep of
`unit_tests/commit_guardian/`, `unit_tests/build_guards/`, and `tests/` (2051 passed, 5
skipped, 1 xfailed, 142 subtests, exit 0) before signing off — I do not have residual doubt
about the fix as it now stands, but flagging the miss itself: my own "verify before trusting
green" diligence caught the test-passing state but not the semantic regression until the
coordinator pointed at the specific line, which is exactly the kind of thing this epic
exists to catch even in remediation work.

### 2026-08-25 13:40 — python-coder (status: ok)
feedback-id: fb_2026-08-25_d5f38a63
completion_manifest:
  shared_worktree_hazard_removed: true
  real_full_build_preserved: true
  vacuity_guard_added: true
  isolation_verified_by_git_status_diff: true

## Python-Coder — Isolation Fix for test_bp_100k_3_i.py

**Hazard removed.** `test_bp_100k_3_i.py`'s `setUpClass` previously ran the real build
directly against this worktree's own root (`--target-dir <this worktree>`). This
worktree's `.leafcutter` is a symlink into a directory shared by every other worktree in
the workspace, so running this one test file rewrote the deployed toolchain out from
under everything else running concurrently, and dirtied `docs/agents/cards/*.card.md` on
every run (KI-BP-002). `setUpClass` now builds into a fresh `tempfile.TemporaryDirectory`
instead — no file under this worktree is written to at test time.

**How the AC's "real freshly built tree, not a synthesized subset" constraint is kept.**
`setUpClass` copies the REAL `templates/`, `scripts/`, and `config/` trees (reusing
`unit_tests/build_guards/test_bp_100k_2.py`'s `_build_synthetic_full_package` via
`importlib`, rather than a second hand-authored copy) into the same supported consumer
layout `build-self.sh` itself uses, then invokes the REAL `python
<tmp>/leafcutter-ai/scripts/build.py --target-dir <tmp>` as a subprocess — the actual
CLI entry point, every phase, none hand-picked or omitted. The four tests then execute
the DEPLOYED hook copies this build produced (`<tmp>/scripts/commit_guardian/*.py`),
never the templates/ source. Added a setup sanity check that fails the class if the
resulting manifest's `output_mappings` is empty, so the tests cannot pass vacuously over
zero artifacts — the exact failure mode this epic exists to catch. Verified:
`AC_ENFORCE_STRICT=1 pytest test_bp_100k_3_i.py` — 4 passed in 5.48s; `ruff check` clean;
`git -C <worktree> status --short` captured before and after the run and diffed
byte-identical (including no new churn in `docs/agents/cards/`), confirming the isolation
actually holds and is not merely intended.

**Residual gap — read before trusting this as fully equivalent to a real worktree
build.** The isolated build is materially better than a hand-authored fixture (it is the
unmodified build.py CLI running every phase over an unmodified copy of every real
template), but it is not identical to running the build in the actual shared worktree,
and I want that stated plainly rather than implied away:
- The copied package root has no `.git` directory. Every git-dependent code path in
  `build.py` — `_check_tracked_source_guard`'s tracked-source check, the halt-guard's
  pinned-SHA lookup, and the changelog-driven `_compute_version_str` tag/entry scan — is
  therefore exercised only on its "not a git repo / first run" no-op branch (each wrapped
  in try/except and confirmed non-fatal by reading `scripts/release/compute_next_version.py`
  and `scripts/build_halt_guard.py` before writing this fix), never on the branch that
  actually walks git history the way a real self-hosted build does. If one of those
  git-active branches were broken, this test would not catch it.
- The build lands in an **empty** target directory, so this is a fresh-install run, not
  an idempotent rebuild-in-place: there is no pre-existing `.build_manifest.json` to diff
  against, no compare-before-write skip logic exercised, and none of the real workspace's
  `.leafcutter` symlink topology is present. Anything specific to rebuilding over existing
  state is untested here.
- Only `templates/`, `scripts/`, and `config/` are copied. If any build phase reads a file
  elsewhere under the real package root (e.g. `changelogs/`), that path is simply absent
  from the isolated copy.

I am confident this change removes the hazard without weakening the AC's specific
"not a synthesized subset" wording (every template is real and unabridged, every phase
runs for real). I am NOT claiming the isolated run is a strict superset of what a
real-worktree build would exercise — the three gaps above are real, and if the shared
worktree's git/incremental-rebuild code paths are ever the thing under test, this fixture
will not see them.
