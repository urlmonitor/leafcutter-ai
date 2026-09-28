---
title: "KI-TQ-20260928-windows-pytest-collection-flake — on this Windows machine a freshly written test file intermittently fails pytest collection with WinError 2, so the red-baseline and done-proof gates report inconclusive for an environmental reason"
description: "medium — about one run in two or three under load, pytest exits 2 with 'FileNotFoundError: [WinError 2]' during collection of a just-written temp test file. Reproduced with bare python -m pytest and no leafcutter code. The gates correctly refuse to read an exit-2 run as a verdict, so the effect is a false 'inconclusive' or 'stale' that a per-file rerun clears. Environment only: Linux CI is unaffected."
type: reference
category: reference
status: active
created: '2026-09-28'
last_updated: '2026-09-28'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/testing-quality/open-high-ki-tq-20260927-windows-local-runs-disagree-with-linux-ci.md
---

# KI-TQ-20260928-windows-pytest-collection-flake — on this Windows machine a freshly written test file intermittently fails pytest collection with WinError 2, so the red-baseline and done-proof gates report inconclusive for an environmental reason

- **Severity:** medium. Environment, not product logic. It makes local gate verdicts unreliable (an honest "could not tell" when there was an answer to be had), but it never produces a false pass. CI on Linux is unaffected.
- **Status:** open. No AC. Cause not confirmed.
- **Occurrences:** several in one session (2026-09-25..28, Windows 11); roughly one run in two or three under load. Session observation.
- **First seen:** 2026-09-25 · **Last seen:** 2026-09-28
- **Where:** the pytest subprocess in `scripts/ac_store/done_proof.py` `_run_pytest_and_parse` (`:1260`), which the fast lane's `verify_red_baseline` also uses (`scripts/build_orchestration/fast_lane.py:366-368`)

## Symptom (session observation)

A test file that has just been written, typically under a temp directory, fails collection:

```text
FileNotFoundError: [WinError 2] The system cannot find the file specified
```

The inner pytest exits 2. Re-running the same file on its own, a moment later, collects and runs normally. It was reproduced with a bare `python -m pytest` on a throwaway test file, with no leafcutter code on the path, so the package is not the cause.

## How the gates react (verified in code, main 8ed47463)

`_run_pytest_and_parse` treats any return code other than 0 or 1 as an unfinished run: *"pytest run unfinished: N file(s), returncode 2"* (`done_proof.py:1367-1370`). It returns `_PYTEST_RUN_INCOMPLETE_SENTINEL` instead of outcomes. Red-baseline therefore reports the tests as inconclusive, and mark-done reports them as not verified ("stale" in the session). That is the correct fail-closed reaction. The problem is only that it happens for no reason connected to the change.

## Likely cause (not confirmed)

File-system latency right after the write: antivirus scanning or indexer handles on a new file, or a directory in pytest's rootdir/conftest walk that is being created or removed at the same time. `_run_pytest_and_parse`'s own docstring records the second shape: a rootdir walk that *"can cross unrelated, transiently-changing directories and fail collection outright with a spurious `FileNotFoundError`"*. BO-2900a-3 fixed that by anchoring the child's `cwd` (`_resolve_pytest_run_cwd`). Since the bare-pytest reproduction still flakes, that anchoring does not remove all of it.

## Distinct from

`KI-TQ-20260927-windows-local-runs-disagree-with-linux-ci` lists deterministic Windows failures (cmd.exe, chmod, `resource`, cp1252, MSYS paths). This one is intermittent and clears on rerun. `KI-TQ-20260927-full-pytest-run-has-114-collection-errors` is a deterministic import-path collection error.

## Detection

A gate verdict of inconclusive / unfinished with `returncode 2` whose pytest output shows `WinError 2` during collection, and which passes on a per-file rerun.

## Workaround

Re-run the affected file on its own before believing an inconclusive or stale result. If the test has to be run many times, excluding the repo and temp directories from real-time antivirus scanning may help (untested).

## Suggested fix

1. In `_run_pytest_and_parse`, when the return code is 2 and the output contains a collection-time `FileNotFoundError`, retry once after a short delay before returning the incomplete sentinel. Report that a retry happened, so the flake is counted rather than hidden.
2. Confirm the cause before building more: run the bare reproduction with Defender exclusions on and off, and with `-p no:cacheprovider`, and note which change removes it.

**Pattern:** an environmental fault that the gates correctly refuse to read as a verdict. The failure is safe, but it trains people to rerun until green without looking at why.
