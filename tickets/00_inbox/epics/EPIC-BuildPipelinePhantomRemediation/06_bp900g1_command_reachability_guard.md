---
title: "Build a real command-reference reachability guard (path-form fails, name-form via registry passes)"
status: done
components:
  - build_pipeline
created: 2026-07-14
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
change_target: pipeline
risk_surface: contract_boundary
source_ac: BP-900g-1
ac_coverage:
  - BP-900g-1
  - BP-900g-1-i
files_touched:
  - scripts/build_phases.py
  - scripts/build.py
  - unit_tests/build_guards/test_command_reachability_guard.py
agents:
  architect-review: needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: signed_off
  pull-request: needed
---

# 06: Command-reference reachability guard (not just the name-based workaround)

## Actor / Goal

As `build.py`/`build_phases.py`, I want a real command-reference reachability check that,
at build time, resolves every command `Workflow(...)`/`Skill(...)` handoff target against
the actual post-deploy layout and **fails the build** when a target does not resolve — so
BP-900g-1 is enforced by a guard, not merely worked around, and a name-based reference that
resolves via the registry (BP-900g-1-i) passes.

## Remediation Context (audit 2026-07-14)

**TEST_NO_CODE — guard missing, only the workaround is asserted.** The BP-900g-1 finding
was addressed by switching command templates to the name-based `Workflow("build-feature")`
form (EPIC-DeployCollision), and `unit_tests/build_guards/test_deploy_collision_guard.py`
asserts that workaround (e.g. `templates/commands/build-feature.md` must contain
`Workflow("build-feature")` NOT `Workflow("scripts/workflows/build-feature.js")`). But the
AC's actual requirement — a **build-time command-reference reachability check** that fails
when a handoff target does not resolve to a deployed artifact — was never built. The store
is phantom-done: the workaround hides the absence of the guard, so a future path-form
regression (`Workflow("scripts/workflows/...js")`, which does not resolve because workflow
`.js` files deploy to `<output_root>/workflows/` via the `.claude/workflows` shim per
BP-811) would not be caught.

**Do: build the guard, don't re-do the workaround.** Add a command-reachability phase to
the build (extend `build_phases.py`; wired from `build.py`): extract each deployed command's
`Workflow(...)` and `Skill(...)` targets, then resolve each against the true post-deploy
layout — a target resolves if EITHER it names a registered workflow/skill in the deployed
registry (name-form) OR it is a path that exists post-deploy. A bare `.js` path under
`scripts/workflows/` must **not** resolve. Emit a verdict listing each unresolvable target
`{ command, target, kind: 'workflow'|'skill', reason }`; a non-empty list fails the build
(non-zero exit) naming the command, the unresolvable target, and that it does not resolve
post-deploy. This is the COMMAND-SIDE analogue of BP-811 (the shim); **do not modify or
re-parent BP-811.** The live regression fixture is
`Workflow("scripts/workflows/build-feature.js")` — a test must pin it as unresolvable, and
`Workflow("build-feature")` (registered) as resolvable.

## Acceptance Criteria

Resolves BP-900g-1, BP-900g-1-i (verbatim Gherkin under
`docs/acceptance-criteria/build_pipeline/BP-900-deployment-completeness/`). Definition of
done: a command with a path-form target that does not resolve post-deploy fails the build
with the named target/reason; a command with a registry-registered name-form target
succeeds; a real test exercises both, distinct from the existing collision-guard workaround
test.

## Test Requirements

```yaml
tests:
  - name: test_ac_bp900g1_pathform_unresolvable_target_fails_build
    file: unit_tests/build_guards/test_command_reachability_guard.py
    covers: [BP-900g-1]
    asserts: Workflow("scripts/workflows/build-feature.js") is flagged unresolvable and the reachability check fails the build naming the command, target, and reason.
  - name: test_ac_bp900g1i_nameform_registry_target_passes
    file: unit_tests/build_guards/test_command_reachability_guard.py
    covers: [BP-900g-1-i]
    asserts: Workflow("build-feature"), a registered deployed-registry entry, resolves and the check passes (zero exit) for that reference.
```

## Sign-offs

- [ ] architect-review
- [x] test-writer — 2026-08-18 17:45
- [x] python-coder — 2026-08-18 18:30
- [ ] test-runner
- [ ] pr-reviewer
- [x] commit — 2026-08-18 19:00
- [ ] pull-request

## Comments

### 2026-08-18 17:45 — test-writer (status: ok)
feedback-id: fb_2026-08-18_6b382c2c
completion_manifest:
  test_ac_bp900g1_pathform_unresolvable_target_fails_build_written: true
  test_ac_bp900g1i_nameform_registry_target_passes_written: true
  red_baseline_confirmed: true
  real_artifact_roundtrip_test_included: true
red_baseline:
  - test_name: test_ac_bp900g1_pathform_unresolvable_target_fails_build
    file: unit_tests/build_guards/test_command_reachability_guard.py
    error: "_CheckerMissing: check_command_reachability not found in build_phases — python-coder must implement this function (BP-900g-1 guardrail)"
  - test_name: test_ac_bp900g1_pathform_target_absent_entirely_also_fails
    file: unit_tests/build_guards/test_command_reachability_guard.py
    error: "_CheckerMissing: check_command_reachability not found in build_phases — python-coder must implement this function (BP-900g-1 guardrail)"
  - test_name: test_ac_bp900g1i_nameform_registry_target_passes
    file: unit_tests/build_guards/test_command_reachability_guard.py
    error: "_CheckerMissing: check_command_reachability not found in build_phases — python-coder must implement this function (BP-900g-1 guardrail)"
  - test_name: test_ac_bp900g1i_unregistered_nameform_target_still_fails
    file: unit_tests/build_guards/test_command_reachability_guard.py
    error: "_CheckerMissing: check_command_reachability not found in build_phases — python-coder must implement this function (BP-900g-1 guardrail)"
  - test_name: test_real_deployed_build_feature_resolves_with_zero_findings
    file: unit_tests/build_guards/test_command_reachability_guard.py
    error: "_CheckerMissing: check_command_reachability not found in build_phases — python-coder must implement this function (BP-900g-1 guardrail)"
  - test_name: test_broken_deployed_tree_yields_ok_false
    file: unit_tests/build_guards/test_command_reachability_guard.py
    error: "_CheckerMissing: check_command_reachability not found in build_phases — python-coder must implement this function (BP-900g-1 guardrail)"
Wrote unit_tests/build_guards/test_command_reachability_guard.py: 6 tests specifying a new `check_command_reachability(output_root) -> list[dict]` contract for build_phases.py, distinct from the existing collision-guard workaround test. Covers both required AC scenarios (path-form Workflow("scripts/workflows/build-feature.js") flagged unresolvable; name-form Workflow("build-feature") resolves via the deployed workflow registry) plus companion negative cases, a mixed-body non-suppression check, and a real-artifact round-trip test that runs the actual build.py (workflows enabled) and asserts the real deployed build-feature.md command resolves cleanly. All 6 tests confirmed RED via `pytest unit_tests/build_guards/test_command_reachability_guard.py -v` (non-zero exit, ImportError-based `_CheckerMissing` failures — no syntax errors, no false-green tests). Pre-existing ticket frontmatter gap noted: `change_target`/`risk_surface` are missing from this ticket's frontmatter (unrelated to this phase's edits; the `ticket_frontmatter_guard` hook fired on every edit here but did not block the write).

### 2026-08-18 18:30 — python-coder (status: ok)
feedback-id: fb_2026-08-18_1808bf0d
completion_manifest:
  check_command_reachability_implemented: true
  handoff_target_resolves_helper_implemented: true
  build_py_wired_to_reachability_guard: true
  red_baseline_all_green: true
  ruff_clean: true
  real_build_sanity_run_ok: true
red_baseline_results:
  - test_name: test_ac_bp900g1_pathform_unresolvable_target_fails_build
    result: green
  - test_name: test_ac_bp900g1_pathform_target_absent_entirely_also_fails
    result: green
  - test_name: test_ac_bp900g1i_nameform_registry_target_passes
    result: green
  - test_name: test_ac_bp900g1i_unregistered_nameform_target_still_fails
    result: green
  - test_name: test_real_deployed_build_feature_resolves_with_zero_findings
    result: green
  - test_name: test_broken_deployed_tree_yields_ok_false
    result: green
Implemented `check_command_reachability(output_root)` and the pure `_handoff_target_resolves()` helper in `scripts/build_phases.py` (BP-900g-1 / BP-900g-1-i): extracts every `Workflow(...)`/`Skill(...)` handoff target from deployed `commands/*.md`, resolves name-form targets via the deployed workflow/skill registry and path-form targets as a literal path against `output_root`, returning one verdict dict per unresolvable target. All 6 red-baseline tests in `test_command_reachability_guard.py` are now green, including the real-artifact round-trip that runs `build.py` for real. Beyond the ticket's `files_touched` list, I also wired the guard into `scripts/build.py` (`_check_command_reachability_guard`, called post-deploy, skipped under `--dry-run`) so the AC's literal requirement ("When build.py runs its command-reference reachability check, Then the build exits with a non-zero status") is actually true end-to-end, not just a callable function — the exact phantom-done pattern this epic remediates. Verified with a full real `build.py` run against a fresh temp target (exit 0, zero reachability findings) plus a manual full-tree scan of all real deployed commands (0 verdicts). Ruff clean on both touched scripts. Pre-existing, unrelated `check_documentation.py` DECISION HISTORY format violations exist on legacy entries in both `build_phases.py` (2026-05-21 entry) and `build.py` (2026-05-22 entry) predating this change — confirmed present on `HEAD` before my edits; left untouched per doc-enforcer §6 (legacy entries must not be retrofitted). architect-review is still `needed` per pre-existing frontmatter; not something this phase can flip.

### 2026-08-18 19:00 — commit (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Committed the ticket's three `files_touched` (`scripts/build_phases.py`, `scripts/build.py`, `unit_tests/build_guards/test_command_reachability_guard.py`) as SHA `20d6b1f6` via a pathspec-scoped `git commit -- <paths>` (the worktree is shared with tickets 07/09/etc mid-flight and staged; those files were left untouched). Pre-commit hooks ran and passed cleanly (no autofix needed); the new test file's 6 tests re-verified green immediately before committing. `scripts/feedback/submit_feedback.py` is absent in this worktree, so `feedback-id` is recorded as `(submit-failed)` per signoff §2a — this is not treated as a phase failure.
