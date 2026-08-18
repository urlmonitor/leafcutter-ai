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
ac_coverage: 6/6
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
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: signed_off
  pr-reviewer: needed
  ac-validator: needed
  ac-fulfillment-gate: signed_off
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

- [x] AC-1: after a real build, the manifest yields a fingerprint for a non-agent template family (BP-100k-1)
- [x] AC-2: the executed template-drift gate emits match-then-drift for that template, never absent-from-manifest (BP-100k-1)
- [x] AC-3: manifest template coverage equals the build's actual copy set (BP-100k-1)
- [x] AC-4: the output mapping resolves a deployed output to the source it was produced from (BP-100k-2)
- [x] AC-5: the executed output-drift gate emits match-then-drift for that output, never unregistered (BP-100k-2)
- [x] AC-6: output-mapping coverage equals the set of files the deploy phases actually wrote (BP-100k-2)

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
| BP-100k-1 | `unit_tests/build_guards/test_bp_100k_1.py` — `TestManifestRecordsNonAgentTemplateFingerprint::test_manifest_records_a_fingerprint_for_a_non_agent_template_family` (L213), `TestDriftGateEmitsMatchThenDrift::test_drift_gate_emits_match_then_drift_for_that_template` (L265), `TestGateNeverReportsManagedTemplateAbsent::test_gate_never_reports_a_managed_template_as_absent_from_manifest` (L329), `TestManifestCoverageEqualsBuildCopySet::test_manifest_coverage_equals_the_build_copy_set` (L364) — 4/4 green | `scripts/build_helpers.py::write_build_manifest()` now also hashes `templates/scripts/commit_guardian/*.py` (diff hunk adding the `cg_templates_dir` block) | covered — 2026-08-18 |
| BP-100k-2 | `unit_tests/build_guards/test_bp_100k_2.py` — `TestOutputMappingNamesDeployedOutputAndSource::test_output_mapping_names_the_deployed_output_and_its_source` (L272), `TestOutputDriftGateEmitsMatchThenDrift::test_output_drift_gate_emits_match_then_drift_for_that_output` (L330), `TestGateNeverReportsBuildProducedOutputUnregistered::test_gate_never_reports_a_build_produced_output_as_unregistered` (L399), `TestOutputMappingCoversEveryDeployPhaseOutput::test_output_mapping_covers_every_deploy_phase_output` (L433) — 4/4 green | `scripts/build_helpers.py::_compute_output_mappings()` reworked to key every family at the canonical shim-resolved path via the shared `shim_map` table and `_canonicalize_output_path()` | covered — 2026-08-18 |

## Sign-offs

- [x] architect-review — 2026-08-18 14:00
- [ ] test-writer
- [x] python-coder — 2026-08-18 17:15
- [ ] test-runner
- [x] documentation-expert — 2026-08-18 18:00
- [ ] pr-reviewer — failed 2026-08-18 17:20
- [ ] ac-validator
- [x] ac-fulfillment-gate — 2026-08-18 19:30
- [ ] commit — failed 2026-08-18 20:15
- [ ] pull-request

## Comments

### 2026-08-18 14:00 — architect-review (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  blast_radius_analyzed: true
  rubric_criteria_evaluated: true
  small_large_classification: true
Classified small: 3 touched files (scripts/build_helpers.py + 2 new test files), single component (build_pipeline), no cross-module boundary crossed, and no always-large trigger fired (no Alembic migration, no hypertable change, no FastAPI surface change, no ADR-contract file touched — confirmed no ADR references build_manifest/output_mappings). No research-agent/Agent tool was available in this invocation's toolset, so blast-radius analysis was performed directly via Read/grep against write_build_manifest(), _compute_output_mappings(), and the two drift-gate scripts (check_build_drift.py, check_output_drift.py) rather than by spawning research-agent — noting this as a process deviation for the record. requires_adr and requires_diagram remain false as already set in frontmatter.

### 2026-08-18 16:30 — test-writer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  tests_written_for_all_8_test_requirements_rows: true
  red_baseline_captured: true
  behavioral_not_grep_only: true
  no_second_hardcoded_inventory_assumed: true

## Test Writer — Completion Report

### Tests Written
| File | Directory | Framework | Status |
|---|---|---|---|
| test_bp_100k_1.py | unit_tests/build_guards/ | unittest | written (4 tests, all red) |
| test_bp_100k_2.py | unit_tests/build_guards/ | unittest | written (4 tests, all red) |

### Verification Run
- Command: `python -m unittest discover -s unit_tests/build_guards -t . -p "test_bp_100k_1.py"` and same for `test_bp_100k_2.py`
- Result: red — 4/4 failures in each file (8/8 total). All failures are `AssertionError` (no `ImportError`/`SyntaxError`/collection errors). Ran in 0.43s (file 1) and 8.12s (file 2).

### Approach
Both ACs explicitly forbid grep-only verification ("do not grep the manifest writer's source") and forbid presuming the fix shape (no second hardcoded inventory). Per that constraint, every test builds a synthetic package root containing REAL, `shutil.copytree`'d (never paraphrased) `templates/`/`scripts/`/`config/` trees, calls the REAL `write_build_manifest()` / `build_phases.*` / `install_shims()` imported from this worktree's own `scripts/` (or, for `build_phases.py` specifically — which resolves its own package root from `__file__` at import time — via `importlib.util.spec_from_file_location` under a unique module name each time, so it always reads the current synthetic copy rather than a `sys.modules`-cached one from another test file), and then either (a) asserts on the real, derived expected set (never a fixed count or hand-typed file list), or (b) deploys a real, byte-identical copy of `check_build_drift.py` / `check_output_drift.py` into a synthesized `.leafcutter/scripts/commit_guardian/` layout and runs it as a subprocess exactly as pre-commit does — the same proven pattern as `unit_tests/commit_guardian/test_ge_118b_drift_manifest_resolution.py`.

Confirmed empirically before writing any assertion (see module docstrings and ticket Remediation Context): the real defect is dual — (1) `template_hashes` never includes `templates/scripts/commit_guardian/*.py` (0/87 present), and (2) `output_mappings` keys are computed as `agents/README.md` (missing the `.claude/` prefix the real deploy+shim path carries), so a real full build+shim+manifest run showed 0/81 real deployed files matched by key. Both symptoms are reproduced verbatim by the red baseline below.

### Notes
No new test directories were needed (`unit_tests/build_guards/` already exists). Two ephemeral scratch directories I created directly under the shared `worktrees/` parent while empirically confirming the defect by hand (`tmp4xr_0fd7`, `tmpa_ks00u4`) could not be removed — my `rm -rf` was denied by the permission system — flagging here for manual cleanup; they are untracked, outside any git tree, and harmless.

red_baseline:
  - test_name: test_manifest_records_a_fingerprint_for_a_non_agent_template_family
    file: unit_tests/build_guards/test_bp_100k_1.py
    error: "AssertionError: 'leafcutter-ai/templates/scripts/commit_guardian/check_ac_circular_deps.py' not found in {...61 agents/*.md keys..., 'output_mappings': {}} : write_build_manifest() did not record a fingerprint for 'leafcutter-ai/templates/scripts/commit_guardian/check_ac_circular_deps.py' (a commit-guardian hook template — a template family other than templates/agents/*.md)."
  - test_name: test_drift_gate_emits_match_then_drift_for_that_template
    file: unit_tests/build_guards/test_bp_100k_1.py
    error: "AssertionError: 'leafcutter-ai/templates/scripts/commit_guardian/__init__.py not in manifest' unexpectedly found in stderr — check_build_drift.py reported the non-agent template as absent from the manifest instead of yielding a match verdict."
  - test_name: test_gate_never_reports_a_managed_template_as_absent_from_manifest
    file: unit_tests/build_guards/test_bp_100k_1.py
    error: "AssertionError: 'not in manifest' unexpectedly found in stderr (every commit-guardian template reported absent)."
  - test_name: test_manifest_coverage_equals_the_build_copy_set
    file: unit_tests/build_guards/test_bp_100k_1.py
    error: "AssertionError: {87 commit-guardian keys} != {} : Missing from manifest: ['leafcutter-ai/templates/scripts/commit_guardian/__init__.py', '.../_ac_pattern_deletion_guard.py', ...]. Unexpected extra keys: []."
  - test_name: test_output_mapping_names_the_deployed_output_and_its_source
    file: unit_tests/build_guards/test_bp_100k_2.py
    error: "AssertionError: '.claude/agents/README.md' not found in {'agents/README.md': {...}, ...} : output_mappings has no entry for '.claude/agents/README.md' — today's _compute_output_mappings() keys entries as 'agents/README.md' (missing the '.claude/' prefix)."
  - test_name: test_output_drift_gate_emits_match_then_drift_for_that_output
    file: unit_tests/build_guards/test_bp_100k_2.py
    error: "AssertionError: '.claude/agents/README.md not in output_mappings' unexpectedly found in stderr — check_output_drift.py reported the deployed agent definition as absent from output_mappings instead of yielding a match verdict."
  - test_name: test_gate_never_reports_a_build_produced_output_as_unregistered
    file: unit_tests/build_guards/test_bp_100k_2.py
    error: "AssertionError: 'not in output_mappings' unexpectedly found in stderr (all 59 real deployed agent files reported absent)."
  - test_name: test_output_mapping_covers_every_deploy_phase_output
    file: unit_tests/build_guards/test_bp_100k_2.py
    error: "AssertionError: {81 real deployed output paths across agents/commands/hooks} is not false : 81 of 81 real deployed output file(s) across 3 distinct deploy phases are not recorded in output_mappings."

### 2026-08-18 17:15 — python-coder (status: handoff)
feedback-id: (submit-failed)
completion_manifest:
  red_baseline_all_8_tests_green: true
  no_second_hardcoded_inventory_introduced: true
  error_handling_policy_followed: true
  doc_enforcer_manual_check: true
  complexity_reduction_applied: true
  full_regression_sweep_run: true
  one_collateral_test_conflict:
    result: false
    reason: "unit_tests/test_build_workflow_output_paths.py::test_compute_output_mappings_workflow_js_uses_correct_output_key (an older, unrelated TICKET-20260602 regression test) asserts _compute_output_mappings() must NOT prefix workflow-js output keys with '.claude/workflows' — the exact opposite of what BP-100k-2 requires (check_output_drift.py's own main() scans repo_root/.claude/workflows and keys by that path; unit_tests/build_guards/test_bp100_drift_docs_compile.py::TestBP100b5DriftHookScansClaudeWorkflows already independently assumes the canonical '.claude/workflows/<name>' key as ground truth, confirming the old test is stale, not production)."
    remediation: "Respawn test-writer to update test_compute_output_mappings_workflow_js_uses_correct_output_key's assertions (and its target_root/package_root fixture, which currently sets target_root != package_root.parent, an invariant no real build.py invocation produces) to expect the canonical '.claude/workflows/<name>' key introduced by BP-100k-2. Do not weaken or delete the test — only its keying assumption is stale."

red_baseline_results:
  - test_name: test_manifest_records_a_fingerprint_for_a_non_agent_template_family
    result: green
  - test_name: test_drift_gate_emits_match_then_drift_for_that_template
    result: green
  - test_name: test_gate_never_reports_a_managed_template_as_absent_from_manifest
    result: green
  - test_name: test_manifest_coverage_equals_the_build_copy_set
    result: green
  - test_name: test_output_mapping_names_the_deployed_output_and_its_source
    result: green
  - test_name: test_output_drift_gate_emits_match_then_drift_for_that_output
    result: green
  - test_name: test_gate_never_reports_a_build_produced_output_as_unregistered
    result: green
  - test_name: test_output_mapping_covers_every_deploy_phase_output
    result: green

(classification: test_drift)

Implemented BP-100k-1 (Direction A now also hashes `templates/scripts/commit_guardian/*.py`, mirroring check_build_drift.py's own two-directory scan) and BP-100k-2 (Direction B/`_compute_output_mappings()` now keys every entry — agents, commands, workflows, hooks, skills, rules, workflow-js — at the CANONICAL, shim-resolved path check_output_drift.py actually scans, e.g. `.claude/agents/README.md`, `.agents/rules/foo.md`) in `scripts/build_helpers.py`. The agents/commands/workflows/hooks families are derived from `build_phases._compute_phase_mappings()` (build.py's own collision-guard enumeration) rather than a second hand-written inventory, and translated to canonical paths via a `shim_map` table now shared verbatim between `install_shims()` and `_compute_output_mappings()` (previously two independent copies existed only inside `install_shims()`). All 8 red-baseline tests are green; a full `unit_tests/` regression run (3394 tests) found exactly one new conflict, classified above as `test_drift` (production is correct, confirmed against two independent real consumers) — handing off to test-writer for that assertion-only fix. `docs/acceptance-criteria` traceability, `## AC References` checkboxes (AC-1..AC-6), and the `## AC Coverage` table are unaffected by python-coder per this ticket's v1 (non-Agent-Contracts) format. Did NOT delete, skip, or weaken the conflicting test — it remains red pending test-writer's assertion fix, per the contract-shrinkage guard.

### 2026-08-18 18:00 — documentation-expert (status: ok)
feedback-id: fb_2026-08-18_2dc27a22
completion_manifest:
  doc_written: true
  cross_links_added: true
  diataxis_genre_correct: true
Updated `docs/build-drift-hook.md` (the single existing doc surface that documents Direction A/B manifest behaviour, verified via `grep -rl write_build_manifest\|output_mappings\|template_hashes docs/`) — a `how-to`, matching this ticket's genre. Four stale sections corrected against the actual `scripts/build_helpers.py` diff: (1) "Scope" — Direction A now scans two template trees, not just `templates/agents/`; (2) "Output directories covered" table — added the `.claude/hooks/` and `.claude/workflows/` rows check_output_drift.py already scanned but the table omitted, and explained the canonical (post-shim) keying fix that makes `output_mappings` entries actually resolve; (3) §5.2 — corrected the description of `write_build_manifest()`'s two-explicit-tree scan (it does not auto-enumerate every template dir); (4) §5.4 checklist row 2 — clarified that agents/commands/workflows/hooks coverage is now derived automatically via `shim_map` + `build_phases._compute_phase_mappings()`, while skills/rules/workflow-js-shaped categories still need an explicit scanning block. Added §7 reference entries for `scripts/build_helpers.py`, the BP-100k-1/-2 AC YAML, and the two new test files for traceability. Did not touch `## AC References` checkboxes or the `## AC Coverage` table — this is a v1 (non-Agent-Contracts) ticket, so §2c of the signoff skill is skipped, consistent with python-coder's prior comment. No Agent tool was available in this invocation to dispatch a `how-to-author` sub-agent, so the how-to update was authored directly rather than delegated.

### 2026-08-18 17:20 — pr-reviewer (status: blocker)
feedback-id: fb_2026-08-18_b0db643b
completion_manifest:
  bp_100k_1_and_2_tests_verified_green: true
  full_regression_run_completed: true
  collateral_regression_confirmed_via_stash_diff: true
  new_tests_are_behavioral_not_grep_only: true
  merge_blocking_regression_unresolved:
    result: false
    reason: "unit_tests/test_build_workflow_output_paths.py::test_compute_output_mappings_workflow_js_uses_correct_output_key is RED in a full unit_tests/ run against this diff (confirmed independently of python-coder's own report: reproduced, then re-verified by `git stash push -- scripts/build_helpers.py` + re-run, which showed the SAME test passing red-for-a-different-reason is not the case — it does not fail at all without this diff, i.e. this diff is the sole cause). python-coder's 2026-08-18 17:15 comment already diagnosed this correctly as a stale test assumption (production's new '.claude/workflows/<name>' key is correct; the old test asserts the opposite) and explicitly handed off to test-writer to update the assertion — but frontmatter still shows `test-writer: needed` and no follow-up edit to unit_tests/test_build_workflow_output_paths.py exists in the working tree. The handoff was never completed."
    remediation: "Respawn test-writer to update test_compute_output_mappings_workflow_js_uses_correct_output_key (and its target_root/package_root fixture) per python-coder's own remediation note in the 17:15 comment: expect the canonical '.claude/workflows/<name>' key, not the old un-prefixed 'workflows/<name>' key. Do not delete or weaken the test — only its keying assumption is stale. Re-run the full unit_tests/ suite after the fix to confirm zero new failures, then re-invoke pr-reviewer."

## Review Report

**Base:** working tree vs `HEAD` (branch `EPIC-BuildPipelinePhantomRemediation`)
**Diff size:** `scripts/build_helpers.py` +270/-48 lines; plus 2 new test files (`unit_tests/build_guards/test_bp_100k_1.py`, `test_bp_100k_2.py`, 8 tests total) and a documentation update to `docs/build-drift-hook.md`. `pr-review-toolkit:review-pr` and the `Agent` tool were not available in this invocation's toolset, so the review below was performed directly via `Read`/`Bash` (running the tests, diffing against a stashed baseline, and reading the production diff line-by-line) rather than by dispatching the skill's sub-agent fan-out — noting this as a process deviation for the record, consistent with the same deviation architect-review and documentation-expert already logged earlier in this ticket.

### High-Confidence Findings

[H-1] unit_tests/test_build_workflow_output_paths.py:214 — collateral test regression left unresolved
      `test_compute_output_mappings_workflow_js_uses_correct_output_key` asserts `_compute_output_mappings()` must key workflow-JS outputs as `workflows/<name>` (no `.claude/` prefix) — the exact opposite of what this ticket's fix does (BP-100k-2 re-keys every output family, including workflow-js, to the canonical `.claude/workflows/<name>` path `check_output_drift.py` actually scans). Confirmed via `git stash push -- scripts/build_helpers.py` + re-run: the test passes without this diff and fails with it, so this diff is the sole and direct cause. python-coder's own 2026-08-18 17:15 comment already identified this exact test and correctly diagnosed production as right and the old test as stale (cross-checked against two independent real consumers), and explicitly hedged the ticket as `(status: handoff)` to test-writer for an assertion-only fix — but that follow-up was never made: `test-writer` is still `needed` in frontmatter and the test file is unchanged in the working tree. A ticket cannot be signed off by pr-reviewer while a test it directly caused to fail remains red in the full suite; per this repo's own CLAUDE.md convention ("path-change without full test-grep... a single path change must update every asserting test in one pass"), the stale assertion must be corrected in the same change.
      Sub-skill: manual (pr-review-toolkit unavailable) — verified by direct pytest execution + git stash bisection.

### Medium-Confidence Findings

None found at medium confidence. (One low-probability code-quality note is noted in the suppression tally below rather than surfaced as a finding, since it has no demonstrated correctness impact.)

### Suppression Tally

Suppressed: 1 low-confidence nit (`_load_build_phases_module`'s per-call unique module name is derived from Python's randomized `hash()` of a path string rather than a monotonic counter or `id()` — astronomically low collision risk within a single process, no demonstrated failure, style/robustness nit only), 0 medium findings dropped by Opus. Run `/pr-review explain 1` to re-examine H-1 in detail.

## Escalation

Branch: none
Reason: not escalated — medium count was 0 (threshold > 3); the one merge-blocking issue (H-1) is a clear-cut, independently-confirmed regression, not an ambiguous cluster requiring a second opinion.

## Independent Verification Performed

- Ran `unit_tests/build_guards/test_bp_100k_1.py` and `test_bp_100k_2.py` directly: 8/8 green, confirming AC-1 through AC-6 are behaviorally satisfied (real templates copied via `shutil.copytree`, real `write_build_manifest()`/`build_phases.build_agents()`/`install_shims()` invoked, real `check_build_drift.py`/`check_output_drift.py` run as subprocesses against real deployed artifacts with a match-then-mutate-then-drift assertion pattern — no grep-only or mock-only coverage, satisfying the ticket's "Verify behaviorally" constraint and the repo's durable-side-effect round-trip bar).
- Ran the full `unit_tests/` suite (3474 passed, 128 failed, 30 skipped, 25 xfailed, 1 error, 182.61s). Diffed the failure set against a `git stash` baseline with `scripts/build_helpers.py` reverted: 127 of 128 failures reproduce identically without this diff (pre-existing baseline noise in `commit_guardian`/`feedback` test suites, matching this repo's documented pre-existing-CI-failure baseline) — only `test_compute_output_mappings_workflow_js_uses_correct_output_key` (H-1) is new and attributable to this diff.
- Read the full `scripts/build_helpers.py` diff line-by-line: confirmed the new `shim_map` module-level table, `_load_build_phases_module`, `_template_family`, `_canonicalize_output_path`, and `_render_phase_source` correctly mirror the corresponding real rendering steps in `build_agents`/`build_commands`/`build_workflows`/`build_hooks` (verified by reading those functions in `scripts/build_phases.py` and comparing byte-for-byte the render pipeline each uses). Verified the code comment's claim that `tests/test_build_artifact_parity.py::TestShimMapCoversAllUserFacingCategories` AST-parses `shim_map` from `build_helpers.py`, including its `AnnAssign` (type-annotated) form — confirmed the test's AST walker explicitly handles both `Assign` and `AnnAssign`, so the module-level promotion of `shim_map` does not break that structural test (it still passes).
- Confirmed the new try/except in `_compute_output_mappings()` around `_load_build_phases_module`/`_compute_phase_mappings()` names specific exception types (`OSError, ImportError, AttributeError, ValueError`) and logs via `_warn(...)`, meeting this repo's error-handling policy (no bare/silent excepts).
- Confirmed this is a v1 ticket (no `## Agent Contracts` section) — contract-aware mode, cross-file contract tracing, and the AC Coverage table `Validated` column fill do not apply.
- Confirmed no `agent_registry.json` or agent-card files are touched by this diff — Step 2a (card/registry backstop) does not apply. Confirmed no `agent()`-style dispatch calls are touched — Step 2b (dispatch instruction lens) does not apply. Confirmed the durable side-effect (build manifest + deployed outputs) has genuine real-effect round-trip test coverage (writes then reads back real artifacts, not mock/topology-only assertions) — Step 2c passes unflagged.

### 2026-08-18 19:10 — ac-validator (status: blocker)
feedback-id: (submit-failed — `submit_feedback.py` is not present under this worktree's `scripts/` tree, only under `templates/scripts/feedback/`)
completion_manifest:
  all_six_acs_have_implementation_and_test_evidence: true
  ac_coverage_table_filled: true
  ac_checkboxes_flipped: true
  ac_coverage_frontmatter_updated: true
  store_alignment_script_present:
    result: false
    reason: "scripts/commit_guardian/check_v2_ac_store_alignment.py does not exist in this worktree (only templates/scripts/commit_guardian/ has it, pre-deploy) — treated as pre-store-install per the ac-validator contract's silent-skip rule, not a finding."
    remediation: "n/a — no action required; re-check after next build.py deploy if the gate is expected to be live."
  ticket_ready_for_commit:
    result: false
    reason: "AC coverage itself is fully satisfied (see below) but this is NOT the same as the ticket being safe to commit. pr-reviewer's 2026-08-18 17:20 comment found a merge-blocking regression (H-1: unit_tests/test_build_workflow_output_paths.py::test_compute_output_mappings_workflow_js_uses_correct_output_key) that python-coder's own 2026-08-18 17:15 comment had already diagnosed and handed off to test-writer to fix — and it is STILL unresolved: I re-ran it myself just now (`python -m pytest unit_tests/test_build_workflow_output_paths.py -q`) and it is still RED with the identical failure pr-reviewer described (production key '.leafcutter/.claude/workflows/build-feature.js' contains '.claude/workflows', which the stale test still asserts must never appear). Frontmatter still shows `test-writer: needed` and `pr-reviewer: failed`; no edit to that test file exists in the working tree."
    remediation: "Respawn test-writer to update test_compute_output_mappings_workflow_js_uses_correct_output_key (and its stale target_root/output_root-conflating fixture) to expect the canonical '.claude/workflows/<name>' key per python-coder's and pr-reviewer's own remediation notes — do not weaken or delete the test. Then re-run the full unit_tests/ suite and re-invoke pr-reviewer before re-invoking ac-validator."

**AC coverage verdict: all 6 ACs covered.** Evidence per AC (git diff HEAD -- scripts/build_helpers.py; both new test files are untracked/unstaged in this worktree, read directly):
- AC-1/AC-2/AC-3 (BP-100k-1): implementation — `scripts/build_helpers.py::write_build_manifest()`, the new `cg_templates_dir` block hashing every `templates/scripts/commit_guardian/*.py` file (mirrors `check_build_drift.py`'s own two-tree scan). Test — `unit_tests/build_guards/test_bp_100k_1.py::TestManifestRecordsNonAgentTemplateFingerprint::test_manifest_records_a_fingerprint_for_a_non_agent_template_family` (L213), `::TestDriftGateEmitsMatchThenDrift::test_drift_gate_emits_match_then_drift_for_that_template` (L265), `::TestGateNeverReportsManagedTemplateAbsent::test_gate_never_reports_a_managed_template_as_absent_from_manifest` (L329), `::TestManifestCoverageEqualsBuildCopySet::test_manifest_coverage_equals_the_build_copy_set` (L364) — re-ran directly, 4/4 green.
- AC-4/AC-5/AC-6 (BP-100k-2): implementation — `scripts/build_helpers.py::_compute_output_mappings()`, rewritten to key every output family (agents/commands/workflows/hooks via `build_phases._compute_phase_mappings()`, skills/rules/workflow-js directly) at the canonical shim-resolved path via the new module-level `shim_map` table and `_canonicalize_output_path()`. Test — `unit_tests/build_guards/test_bp_100k_2.py::TestOutputMappingNamesDeployedOutputAndSource::test_output_mapping_names_the_deployed_output_and_its_source` (L272), `::TestOutputDriftGateEmitsMatchThenDrift::test_output_drift_gate_emits_match_then_drift_for_that_output` (L330), `::TestGateNeverReportsBuildProducedOutputUnregistered::test_gate_never_reports_a_build_produced_output_as_unregistered` (L399), `::TestOutputMappingCoversEveryDeployPhaseOutput::test_output_mapping_covers_every_deploy_phase_output` (L433) — re-ran directly, 4/4 green.

Flipped AC-1..AC-6 checkboxes to `[x]`, filled the `## AC Coverage` table's Test/Implementation/Validated columns (`covered — 2026-08-18` both rows), and set `ac_coverage: 6/6` in frontmatter (was a bare `[BP-100k-1, BP-100k-2]` list — confirmed via reading `scripts/ac_store/ac_coverage_resolver.py` that `ac-fulfillment-gate`'s coverage resolution reads `ac_traceability`, not `ac_coverage`, so this reformat does not affect that downstream gate). **Not** flipping my own `agents.ac-validator` frontmatter entry to `signed_off` or checking my `## Sign-offs` box — despite full AC coverage — because doing so would misrepresent the ticket as commit-ready while a confirmed, still-reproducing regression (H-1) sits open from the immediately preceding phase. Leaving `ac-validator: needed` so the supervisor's failure-adjudication routes back to test-writer per pr-reviewer's own remediation, not forward to `ac-fulfillment-gate`/`commit`.

### 2026-08-18 19:30 — ac-fulfillment-gate (status: ok)
feedback-id: (submit-failed — `scripts/feedback/submit_feedback.py` absent from this worktree, only `templates/scripts/feedback/` has it)
completion_manifest:
  ac_traceability_present_and_interpretable: true
  both_acs_resolved_via_shared_resolver: true
  ac_yaml_fields_verified_and_autofixed: true
  schema_validation_run_after_edit: true
Ran `.leafcutter/scripts/ac_store/ac_coverage_resolver.py` against this ticket's legacy list-form `ac_traceability` block (`{l2: [BP-100k-1, BP-100k-2], l3: [], ac_path: ...}`); it resolved both ACs and reported `work_status`/`covered_by` failures on each (`implemented_by` pointed only at the ticket file itself, not at the actual diff evidence). Confirmed both AC YAML files are `level: L2`, so `implemented_by` and `covered_by` are both required (not optional-empty). Branch/working-tree diff evidence (`git diff HEAD --name-only` + `git status --porcelain`, since the real implementation is still uncommitted ahead of the `commit` phase) showed all three of this ticket's `files_touched` present: `scripts/build_helpers.py`, `unit_tests/build_guards/test_bp_100k_1.py`, `unit_tests/build_guards/test_bp_100k_2.py`. Auto-fixed both `BP-100k-1.yaml` and `BP-100k-2.yaml` (append-only): `work_status: todo` → `done`; appended the three diff-evidenced files to `implemented_by` (none were previously listed beyond the ticket path); appended `covered_by` from a `# covers: BP-100k-1` / `# covers: BP-100k-2` tag found directly in `unit_tests/build_guards/test_bp_100k_1.py` / `test_bp_100k_2.py` respectively (this repo's actual test convention — `tests/` itself had no covers-tag hits). `scripts/commit_guardian/check_ac_schema.py` is absent from this worktree (pre-install), so I instead ran the available `scripts/ac_store/validate_ac_schema.py` against both edited files as a sanity substitute: `OK: all 2 AC YAML files are valid.` Re-ran the resolver after the edits: `ok: true`, zero failures. Note: the unrelated pr-reviewer/ac-validator-flagged H-1 collateral-test regression (`test_compute_output_mappings_workflow_js_uses_correct_output_key`) is out of this gate's scope (AC YAML field accuracy only, not overall commit-readiness) and remains unresolved — `ac-validator` is still `needed` in frontmatter, so the ticket does not advance past that gate regardless of this sign-off.

### 2026-08-18 20:15 — commit (status: blocker)
feedback-id: (submit-failed — `scripts/feedback/submit_feedback.py` absent from this worktree, only `templates/scripts/feedback/` has it)
completion_manifest:
  pre_commit_hooks_pass:
    result: false
    reason: "Never reached the pre-commit stage — refused to stage/commit because upstream gate state is not commit-clean."
    remediation: "Respawn test-writer to fix the collateral regression, then re-run pr-reviewer and ac-validator, then re-invoke commit."
  commit_message_valid:
    result: false
    reason: "No commit was attempted."
    remediation: "n/a until upstream gates pass."
  ticket_staged:
    result: false
    reason: "Left the ticket's other files_touched (scripts/build_helpers.py and the two new test files) unstaged; only this sign-off edit to the ticket itself is intended for staging."
    remediation: "Stage the implementation + tests together with this ticket once the blocker below is cleared."
Read the ticket in full before staging anything. Frontmatter shows `pr-reviewer: failed` and `ac-validator: needed` (not `signed_off`) — per the commit agent's supervised-path contract, auto-authorization for the routine confirmation gate requires upstream gates (pr-reviewer, ac-validator, ac-fulfillment-gate) to have actually passed, and that precondition is not met here. Independently re-ran the exact regression pr-reviewer (17:20) and ac-validator (19:10) both flagged as merge-blocking and unresolved: `python3 -m pytest unit_tests/test_build_workflow_output_paths.py -q -k test_compute_output_mappings_workflow_js_uses_correct_output_key` is still RED in this worktree right now, with the identical failure (`'.leafcutter/.claude/workflows/build-feature.js' contains '.claude/workflows'`), confirming the handoff python-coder made to test-writer at 17:15 was never completed — `test-writer` is still `needed` in frontmatter and `unit_tests/test_build_workflow_output_paths.py` has zero diff (`git diff --stat` empty). Refusing to stage or commit `scripts/build_helpers.py` / the two new test files while a confirmed, self-verified regression remains open; committing now would land a diff that breaks an existing test in the full suite. Set `commit: failed` (not `needed`) so the supervisor's failure-adjudication routes back to test-writer per pr-reviewer's and ac-validator's own remediation notes, rather than silently retrying commit. Suggested remediation: respawn test-writer to update `test_compute_output_mappings_workflow_js_uses_correct_output_key` (and its `target_root`/`package_root` fixture) to expect the canonical `.claude/workflows/<name>` key, re-run the full `unit_tests/` suite to confirm zero new failures, re-invoke pr-reviewer and ac-validator, then re-invoke commit.

### 2026-08-18 20:05 — main-loop (status: ok)
feedback-id: fb_2026-08-18_6546c39e

**Blocker cleared. The stale assertion is fixed; this was done by the main loop, not by
test-writer — recorded here so the sign-off is attributable to who actually did it.**

Why the handoff was never executed: `handoff` was a declared value in both drivers'
status enum and read by neither, so python-coder's 17:15 `status: handoff` was recorded
as a completed phase and the loop advanced. That router defect is now fixed and merged
to `main` as `BO-3000` (PR #492, squash `ae5852a2`) — the drivers re-dispatch the named
agent and fail closed on an unparseable target. This ticket's own blocker predates that
fix, so it is resolved by hand here.

**What changed:** `unit_tests/test_build_workflow_output_paths.py` — Test D
(`test_compute_output_mappings_workflow_js_uses_correct_output_key`) now asserts the key
DOES contain `.claude/workflows/`, inverted from the previous assertion that it must not.

**Verified before inverting it, rather than taking the two prior agents' word.** The old
assertion conflated two distinct things: where the build *writes* the file
(`output_root/workflows/<name>` — the BP-811 fix) and how the manifest *keys* that output
for lookup. Confirmed by reading `_OUTPUT_DIRS` in
`templates/scripts/commit_guardian/check_output_drift.py:393`, which scans
`repo_root / ".claude" / "workflows"`. A mapping keyed at the un-prefixed write path is
therefore never matched against a staged workflow JS file, and the gate reports it
unregistered — exactly what BP-100k-2 exists to eliminate. Production is right; the
assertion was stale. Also ran `_compute_output_mappings()` directly to confirm the emitted
key is `<target_root>/.claude/workflows/build-feature.js` rather than inferring it from
the failure text.

The assertion was **not** weakened: it was rewritten as a positive assertion on the
canonical path, with a docstring recording why and a pointer to `_OUTPUT_DIRS` so a future
reader does not re-invert it.

**Results:** `unit_tests/test_build_workflow_output_paths.py` 4/4 green under
`AC_ENFORCE_STRICT=1` — including the three BP-811 tests (A, B, C) that still guard the
write path, confirming the write-path and key-path contracts do not conflict.
`test_bp_100k_1.py` + `test_bp_100k_2.py` 8/8 green.

`test-writer` set to `signed_off` (work done by main loop, per above). `pr-reviewer` and
`commit` reset from `failed` to `needed` so both re-run against the now-clean tree rather
than inheriting a stale verdict.
