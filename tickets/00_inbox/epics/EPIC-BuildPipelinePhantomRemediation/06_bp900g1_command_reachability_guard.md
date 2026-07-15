---
title: "Build a real command-reference reachability guard (path-form fails, name-form via registry passes)"
status: todo
components:
  - build_pipeline
created: 2026-07-14
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
source_ac: BP-900g-1
ac_coverage:
  - BP-900g-1
  - BP-900g-1-i
files_touched:
  - scripts/build_phases.py
  - unit_tests/build_guards/test_command_reachability_guard.py
agents:
  architect-review: needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
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
- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
