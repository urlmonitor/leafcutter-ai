---
title: "The self-healing hook's ordering guard accepts only stage canaries before it and fails closed otherwise"
ac_traceability:
  id: BO-1700c-1-iii
  path: docs/acceptance-criteria/build-orchestration/BO-1700-worktree-quality-gate-guard/BO-1700c-1-iii.yaml
status: todo
components:
  - commit_guardian
  - build_orchestration
created: '2026-10-22'
last_updated: '2026-10-22'
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
change_target: code
risk_surface: safety
complexity: low
requires_adr: false
requires_diagram: false
tags:
  - BO-4300
  - bo4300-hardening
  - A14
  - BO-1700c-1-iii
files_touched:
  - templates/scripts/commit_guardian/ensure_precommit_config.py
  - unit_tests/commit_guardian/test_bo_1700c_1_iii_ordering_guard.py
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  ac-validator: needed
  ac-fulfillment-gate: needed
  commit: needed
---

# 09: The self-healing hook's ordering guard accepts only stage canaries before it and fails closed otherwise

## Actor / Goal
In order for no hook ever to run against a `.pre-commit-config.yaml` that has not been re-materialized
yet, the self-healing hook must check its own place in the manifest. It accepts the stage canaries
(`precommit-canary-*`, which BO-4300c-1-ii places first) ahead of it. It fails the commit closed, naming
the offender, when any other hook is registered before it.

## Context
- **AC:** BO-1700c-1-iii, as amended by A14 (2026-10-22, reason `canary-first-manifest-order`). It follows
  the parent BO-1700c-1's 2026-10-21 amendment: entries before the heal may be stage canaries only.
  - The it_requirement says the guard is "implemented in the self-healing hook (BO-1700c-1)".
  - ADR-001 deployed/template parity applies. The canonical manifest source is
    `templates/scripts/commit_guardian/commit_guardian.json`.
- **Where the guard lives today:** nowhere at run time. A grep of `templates/scripts/commit_guardian`
  finds no ordering check in any hook.
  - The self-healing hook is `templates/scripts/commit_guardian/ensure_precommit_config.py` (282 lines;
    `ensure_config` at line 184, `main` at line 269). It is the only tracked copy; the deployed copy is
    built from it. It never reads the manifest, and its docstrings still say "index 0" (lines 7, 16, 24,
    274).
  - The only ordering check is the test `TestManifestIndex0`
    (`unit_tests/commit_guardian/test_ensure_precommit_config.py:518`). It asserts the real manifest's
    order: `precommit-canary-pre-commit`, `precommit-canary-commit-msg`, `ensure-precommit-config`, ...
  - `verify_precommit_active.py` references canaries, but only to run its own checks in order. It is not
    a manifest-order guard.
- **Limit of a run-time guard.** A hook placed before the heal has already run by the time the heal runs.
  Failing closed therefore means the commit is refused (exit 1), so nothing is committed on the strength
  of a hook that ran against an unrestored config.
- The hook is standalone: no sibling imports (docstring line 11). Keep it so, using only `json` from the
  stdlib.

## Scope
1. Add a pure function `ordering_violation(hook_ids: list[str]) -> str | None` to
   `ensure_precommit_config.py`. It returns None when every entry before `ensure-precommit-config` starts
   with `precommit-canary-`. Otherwise it returns a message naming the first non-canary hook that precedes
   it. A manifest without `ensure-precommit-config` is also a violation.
2. `main()` reads the manifest beside the script (`<script dir>/commit_guardian.json`,
   `hooks_manifest.hooks[*].id`). On a violation, or when the manifest is unreadable, it writes the message
   to stderr and exits 1 (fail closed, never a warning). The heal itself still runs first, so a repaired
   config is not lost.
3. Update the "index 0" docstrings to "first after the stage canaries", and add a DECISION HISTORY entry.

## Acceptance Criteria
- [ ] AC-1: BO-1700c-1-iii (A14, accepted order). With only stage canaries (`precommit-canary-pre-commit`,
  `precommit-canary-commit-msg`) before `ensure-precommit-config`, `ordering_violation` returns None and
  the hook exits 0 with a resolvable config. The real templates manifest passes.
- [ ] AC-2: BO-1700c-1-iii (A14, fail closed, names the offender). With a manifest where `check-secrets`
  precedes `ensure-precommit-config`, whether before or after the canaries, `ordering_violation` names
  `check-secrets`. The hook run as a subprocess exits 1 and its stderr names `check-secrets`.
- [ ] AC-3: BO-1700c-1-iii (fail closed on anything else). A manifest without `ensure-precommit-config`, or
  an unreadable or unparsable manifest, makes the hook exit 1 with a message saying why. It never exits 0
  with a warning.

## Test Requirements

```yaml
tests:
- name: test_only_stage_canaries_before_the_heal_is_accepted
  file: unit_tests/commit_guardian/test_bo_1700c_1_iii_ordering_guard.py
  covers:
  - BO-1700c-1-iii
  asserts: >-
    ordering_violation(['precommit-canary-pre-commit','precommit-canary-commit-msg','ensure-precommit-config','check-secrets'])
    is None, and the ids read from templates/scripts/commit_guardian/commit_guardian.json give None.
  framework: unittest
  type: behavioral
- name: test_other_hook_before_the_heal_fails_closed_naming_it
  file: unit_tests/commit_guardian/test_bo_1700c_1_iii_ordering_guard.py
  covers:
  - BO-1700c-1-iii
  asserts: >-
    Copy ensure_precommit_config.py into a temp dir beside a commit_guardian.json whose hooks are
    [precommit-canary-pre-commit, check-secrets, ensure-precommit-config]. Run it as a subprocess, with a
    temp worktree as cwd that already holds a .pre-commit-config.yaml: it exits 1 and stderr contains
    'check-secrets'. ordering_violation on the same list names check-secrets.
  framework: unittest
  type: behavioral
- name: test_missing_heal_or_unreadable_manifest_fails_closed
  file: unit_tests/commit_guardian/test_bo_1700c_1_iii_ordering_guard.py
  covers:
  - BO-1700c-1-iii
  asserts: >-
    The same subprocess setup with (a) no ensure-precommit-config in the list and (b) a commit_guardian.json
    holding invalid JSON. Each exits 1 with a reason on stderr.
  framework: unittest
  type: behavioral
```

## Sign-offs
- [ ] test-writer
- [ ] python-coder
- [ ] pr-reviewer
- [ ] ac-validator
- [ ] ac-fulfillment-gate
- [ ] commit

## Comments

_(Append-only log -- leave blank when authoring.)_
