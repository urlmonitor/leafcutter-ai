---
title: "fix(ac-store): the store validator no longer passes a run that checked nothing (KI-ACS-001)"
date: "2026-08-25"
time: "06:15"
type: manual
components:
  - ac_store
summary: "validate_ac_schema.py took file paths and did no globbing, so a directory argument matched zero files, printed 'No YAML files to validate.' and exited 0. It now walks a directory recursively and exits non-zero when the arguments resolve to nothing. Pointed at the real store it immediately reports 281 pre-existing violations that the bare-directory form had been reporting as clean."
description: "The script accepted only file paths. Handed a directory — the intuitive way to validate a component, and the form CLAUDE.md itself prescribed from 2026-08-10 to 2026-08-18 — it matched nothing and returned a success-shaped result from a run that had checked nothing. A validator consulted for reassurance that cannot distinguish 'clean' from 'I was given nothing' is worse than no validator. Two changes. First, a directory argument is now walked recursively via _resolve_ac_yaml_paths(), reaching AC YAML at every depth: some records sit directly under a component directory and others inside a feature folder, so a fixed-depth glob like */*.yaml silently skips whole directories — the same no-op in a smaller costume, which is why the walk is rglob rather than a pattern. index.yaml is excluded from discovery, being the component registry rather than an acceptance criterion; naming it explicitly on the command line still validates it, so the exclusion narrows discovery only. Results are de-duplicated so overlapping arguments (a directory plus a file inside it) cannot double-count. Second, files_checked == 0 now prints an explicit error naming the arguments and returns 1 instead of printing 'No YAML files to validate.' and returning 0. Caller compatibility was checked before changing exit semantics rather than after: the only programmatic caller, scripts/check_fixture_schema.py, collects explicit file paths itself and already guards with `if not yaml_files: return []`, so it can never reach the zero-file branch — verified by running it (OK, 4 files). The script is not registered as a pre-commit hook and is not invoked by any CI job; the required 'AC store valid' gate runs templates/scripts/commit_guardian/check_ac_schema.py, a different script that is unaffected. Seven tests, all exercising the real script as a subprocess against a temp store built at two different depths: recursive discovery, a real violation surfacing through a directory walk, zero-resolved-files exiting non-zero, non-YAML-only arguments exiting non-zero, index.yaml exclusion, and two regression guards for the existing explicit-file-path and missing-path contracts. Red baseline before the fix was 4 failed / 3 passed — the three passing were the regression guards, correctly green beforehand. Behavioural confirmation on the real artifact rather than the fixture: `validate_ac_schema.py docs/acceptance-criteria` now reports 281 violations, mostly legacy list-form it_requirements predating the object-form rule, where the same command previously printed a clean no-op. KI-ACS-001 is deleted from docs/known-issues/ac-store.md per the register's own closing protocol, and CLAUDE.md's AC-store hygiene section is rewritten: it had instructed readers NOT to pass a bare directory, which would now steer them away from the correct form."
pr: null
commits: []
---

## Entry

The AC-store validator could not tell "clean" from "I was given nothing."

It took file paths and did no globbing. Hand it a directory — the obvious way to
check a component, and the form `CLAUDE.md` itself prescribed for eight days —
and it matched zero files, printed `No YAML files to validate.`, and exited **0**.

That is the worst possible shape for a tool whose entire job is reassurance.

Two changes:

- **A directory is walked recursively.** AC YAML sits at more than one depth, so
  the walk is `rglob`, not a pattern — a fixed-depth `*/*.yaml` skips whole
  directories, which is the same no-op wearing a different hat. `index.yaml` is
  skipped during discovery (it is the component registry, not a criterion);
  naming it explicitly still validates it.
- **Zero resolved files exits non-zero,** naming the arguments that resolved to
  nothing.

Caller compatibility was checked *before* changing exit semantics. The only
programmatic caller, `check_fixture_schema.py`, collects explicit file paths and
already guards with `if not yaml_files: return []`, so it cannot reach the new
branch — confirmed by running it. The script is registered as no pre-commit hook
and invoked by no CI job; the required **AC store valid** gate runs a different
script and is untouched.

The proof is on the real artifact, not the fixture. Pointed at the store:

```
$ python scripts/ac_store/validate_ac_schema.py docs/acceptance-criteria
... 281 violations
```

The same command used to print a clean no-op. Those 281 are mostly legacy
list-form `it_requirements` predating the object-form rule — real, but not a
fire. The point is that they were always there and the documented defence was
reporting them as absent.

Seven tests, all driving the real script as a subprocess against a temp store
built at two depths. Red baseline was 4 failed / 3 passed; the three passing were
the regression guards, which should have been green beforehand and were.

`KI-ACS-001` is closed and removed from the register. `CLAUDE.md`'s hygiene
section is rewritten — it previously told readers **not** to pass a bare
directory, which would now steer them away from the correct form.
