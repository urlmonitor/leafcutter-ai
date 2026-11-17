---
title: "KI-TQ-20261023-consumer-sweep-full-repo-export — the consumer-sweep check exports the whole base commit to a temp dir on every run that has a test file in scope, even for one changed test and even when the check has already failed"
description: "low — scripts/build_orchestration/_cs_runs.py runs the in-scope test files at the base by extracting git archive of the WHOLE base commit into a temp dir. This happens on every consumer_sweep.py check with at least one changed existing test file, whatever the number of files in scope, and also when the check already stops on an unlisted edit. Measured about 60 s for 14,648 files / 145 MB on a Windows dev machine. Nothing is wrong in the result; the cost is time on every fast-lane finish."
type: reference
category: reference
status: active
created: '2026-10-23'
last_updated: '2026-10-23'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
---

# KI-TQ-20261023-consumer-sweep-full-repo-export — the base run exports the whole repo

> Filed 2026-10-23. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** low. The verdict is right; only the cost is wrong. Each check with a changed
  existing test file pays a full export of the base commit before the base pytest run starts.
- **Status:** open, no AC.
- **Occurrences:** every `consumer_sweep.py check` with an existing test file in scope since
  TQ-500g-3-ii merged. Measured once: about 60 s for 14,648 files / 145 MB on a Windows dev machine.
  `origin/main` now holds 14,870 files.
- **First seen:** 2026-10-23 · **Last seen:** 2026-10-23
- **Where** (line numbers at `origin/main` `ae3a1591c`):
  - `scripts/build_orchestration/_cs_runs.py`:121-140, `_export`. The command is
    `git archive --format=tar <base_sha>` (:123) with no pathspec, so every file of the base commit
    is streamed and extracted (:127, through `_extract_stream`, :112-118).
  - `scripts/build_orchestration/_cs_runs.py`:219-242, `_run_both`. A fresh `mkdtemp` (:221) per
    check, the full export (:224), one base pytest run over the in-scope files (:229), and removal
    of the export (:231). Nothing is cached between checks.
  - `scripts/build_orchestration/_cs_runs.py`:259-265, `run_checks`. The only short cut is "no file
    in scope" (:263-264). One in-scope file triggers the same full export as fifty.
  - `scripts/build_orchestration/consumer_sweep.py`:208-220, `check`. `unlisted` is computed
    (:208) before the runs, but `run_checks` is called unconditionally (:210), so a check that will
    report `reason: "unlisted"` (:213-214) still pays the export and both pytest runs.

## Symptom

`consumer_sweep.py check` (and `wrong_version_gate.py finish`, which calls it at
`scripts/build_orchestration/wrong_version_gate.py`:91) takes about a minute
longer than its pytest runs, even when one test file changed. A `leafcutter_cs_base_*` folder
holding a full copy of the repository appears in the temp dir while it runs.

## Mechanism

1. **The export is sized to the repo, not to the runs.** The base pytest run needs the in-scope
   test files and whatever they import. The export writes everything else too: docs, the AC store,
   changelogs, templates.
2. **No reuse.** The same base sha is exported again on every check of the same work.
3. **No early exit.** The runs are not needed to decide the reason when an unlisted edit already
   stops the check, but they still run so the report is complete.

## Detection

Time `consumer_sweep.py check --test-root <root>` on a change that edits one existing test file,
and compare it with the time of one pytest run of that file.

## Workaround

None needed. Expect the extra minute on large repositories.

## Suggested fix

Directions only; nothing here is applied.

- **Export only what the runs can import.** Pass a pathspec to `git archive`: the in-scope test
  files, their conftest and config files, and the source trees the tests import (for this repo,
  `scripts/`, `unit_tests/` and the root config files). Keep a fallback to the full export when
  the pathspec cannot be derived.
- **Cache per base sha.** Keep the export for a base sha for the life of one finish, or under the
  git dir keyed by sha, and remove it when the work is done. The working tree, index and stash
  stay untouched as today.
- **Skip the runs when the check has already failed.** When `unlisted` is non-empty the reason is
  already decided. The report must stay complete: the TQ-500g-3 tests expect the other lists
  filled when an earlier reason stops the check (for example `loosened` alongside `unlisted` in
  `unit_tests/build_orchestration/test_tq500g3iii_cli.py`:45-70). Check whether any test needs
  `weakened` filled alongside an unlisted stop before taking this option; if one does, take the
  first two options instead.

**Pattern:** a step that needs a few files materialises the whole repository, every time.
