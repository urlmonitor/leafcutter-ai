---
title: The mypy gate has never type-checked most of scripts/
date: "2026-08-31"
time: "06:25"
type: manual
components: 
  - build_pipeline
summary: "Files KI-BP-20260831-0620: the mypy job's scripts/**/*.py pathspec matches nothing directly in scripts/, so 59 of 107 tracked scripts are invisible to it and the job reports SUCCESS for checking nothing."
description: "Register entry only, no code change. The Type-check changed files (mypy) job selects files with a pathspec whose scripts/**/*.py term requires at least one directory below scripts/, so a file sitting directly in scripts/ never matches. Confirmed from two CI logs: PR #611 changed scripts/injection_builders.py and the job type-checked only the four test files, and PR #624 - whose entire purpose was fixing three mypy errors in that same file - logged 'No changed Python files ... skipping mypy' and exited 0. Same empty-scope family as KI-ACS-001."
---

## Entry

The `Type-check changed files (mypy, informational)` job reports SUCCESS in two situations a
reader cannot tell apart: mypy ran and found nothing, and mypy never ran.

The pathspec it selects files with is

```
-- 'scripts/**/*.py' 'tests/**/*.py' 'unit_tests/**/*.py'
```

and `scripts/**/*.py` needs a `/` between the `**` and the `*.py` — so it only matches a file
at least one directory *below* `scripts/`. A file sitting directly in `scripts/` never
matches. Against a real merge that changed three top-level scripts:

```console
$ git diff --name-only --diff-filter=ACM origin/main~1...origin/main -- 'scripts/**/*.py'
$ git diff --name-only --diff-filter=ACM origin/main~1...origin/main -- 'scripts/*.py'
scripts/build.py
scripts/build_helpers.py
scripts/build_phases.py
```

The first prints nothing. **59** tracked `.py` files sit directly in `scripts/` and are
invisible to this gate; 48 in subdirectories are seen. The invisible majority includes
`build.py`, `injection_builders.py`, `roadmap_query.py` and most of the top-level tooling.
`unit_tests/` escapes only because its tests live in subdirectories — the same trap waits for
any test placed directly in `unit_tests/`.

Two instances are confirmed from CI logs rather than inferred:

- **PR #611** changed `scripts/injection_builders.py` plus four test files. The job printed
  `Type-checking changed files:` and then exactly the four `unit_tests/workflows/` paths. The
  script is absent.
- **PR #624** changed that script and a changelog, nothing else, and logged
  `No changed Python files under scripts/, tests/, or unit_tests/ — skipping mypy.` That PR
  existed *specifically* to fix three mypy errors in that file. The check meant to confirm
  the fix never looked at it.

The second is the sharp one: a green mypy check on a PR whose whole purpose was making mypy
green, achieved by not running mypy. (The fix itself is sound — it was verified locally under
the exact CI flags, and the subcommand's output was proven byte-identical before and after.
What was worthless was CI's confirmation of it.)

Worth noting how the errors ever surfaced: not through this pathspec. A test added by
`BO-2400c-1-vii` under `unit_tests/workflows/` imports the module, and mypy followed the
import. So coverage of top-level scripts today is accidental — it depends on whether
something in a matched directory happens to import them, not on what a PR changed.

The fix is a one-line pathspec correction plus a triage of whatever the first honest run
surfaces (the job is `continue-on-error: true`, so that is noise, not a blocker). The second
half matters more: even once fixed, an empty `CHANGED` still emits SUCCESS. That is
legitimate for a PR touching no Python, but it is the *same signal* as a clean run, which is
exactly what let this hide for so long.

This is the `KI-ACS-001` shape again — `validate_ac_schema.py` given a bare directory matched
no files, printed `No YAML files to validate.`, exited 0, and was cited as the defence against
store rot for eight days while checking nothing. **When a gate's scope is computed, the
computation is part of the gate, and an empty scope must never report the same way as a
satisfied one.**
