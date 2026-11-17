---
title: "KI-BO-20261024-list-speed-test-flaky — the writer list speed test compares two single wall-clock runs that are dominated by fixed costs, so its 50-id vs 1-id ratio check fails at random"
description: "low — unit_tests/build_orchestration/test_tq500g1v_list_speed.py::test_writer_list_meets_time_budget_on_real_repo asserts t50 <= 2 x t1 + 1 s from one run each of wrong_version_writer.py list. Both runs are mostly fixed cost (process start, a recursive walk of the test root and a glob of the AC store), so noise on either run decides the result. It failed in CI's proof-of-done job on PR #1330 (run 39990944257) and passed on rerun; locally t1 was 9.1 s and t50 6.8 s."
type: reference
category: reference
status: active
created: '2026-10-24'
last_updated: '2026-10-24'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-20261024-list-speed-test-flaky — a ratio of two single timings

> Filed 2026-10-24. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** low. Nothing wrong is accepted; a rerun clears it. Each false failure costs a CI
  rerun and is blamed on whatever PR is in flight.
- **Status:** open, no AC.
- **Occurrences:** 1 in CI: the proof-of-done job on PR #1330 (run 39990944257) failed on this test
  and passed on rerun. Local runs show how much the single timings move: t1 9.1 s against t50
  6.8 s, the 1-id run slower than the 50-id run.
- **First seen:** 2026-10-23 · **Last seen:** 2026-10-23
- **Where** (line numbers at `origin/main` `849791105`):
  - `unit_tests/build_orchestration/test_tq500g1v_list_speed.py`:28-31, the constants: factor 2.0,
    slack 1.0 s, ceiling 15 s per run.
  - `unit_tests/build_orchestration/test_tq500g1v_list_speed.py`:49-62, `_timed_list`. One wall-clock
    measurement around a fresh `python wrong_version_writer.py list` subprocess.
  - `unit_tests/build_orchestration/test_tq500g1v_list_speed.py`:74-84. One run for 1 id, then one
    for 50 ids, no warm-up, and `assert t50 <= limit` with `limit = 2.0 * t1 + 1.0` (:83-84).
  - `scripts/build_orchestration/_wvr_records.py`:47, `rglob("*.yaml")` over the whole AC store, and
    :146-169, `covers_tags`, an `os.walk` of the whole test root (here the repository root) on
    every list call. These costs do not depend on the number of ids.

## Symptom

`test_writer_list_meets_time_budget_on_real_repo` fails with "list cost grows with the number of
ids: 50 ids may take X s, took Y s", on a change that does not touch the list step. A rerun of
the same commit passes.

## Mechanism

1. **The measured time is mostly fixed cost.** Process start, imports, the AC-store glob and the
   test-root walk are paid once per call whatever the id count. The per-id part the test wants to
   bound is small next to them.
2. **One sample per side.** The test takes one timing of each and compares them. Disk cache,
   another job on the runner or antivirus on Windows can move either sample by seconds. The first
   run also pays the cold cache, which the second run then reuses.
3. **The bound scales with the noisy sample.** A fast 1-id run (warm cache, idle runner) followed by
   a 50-id run that hits a slow moment is enough to break `2 x t1 + 1 s`.

## Detection

A failure of this test with the "list cost grows with the number of ids" message that passes on
rerun, on a PR that does not touch `wrong_version_writer.py`, `_wvw_list.py`, `_wvr_scope.py` or
`_wvr_records.py`.

## Workaround

Rerun the failed job.

## Suggested fix

Directions only; nothing here is applied.

- **Warm up first.** Do one untimed list call before the timed ones, so neither timed run pays the
  cold cache.
- **Take the minimum of several runs** for each id count (for example three), which removes most
  one-off stalls.
- **Or assert an absolute ceiling only.** The 15 s ceiling already catches the original 82 s bug
  on any machine. Drop the ratio, or keep it only as a logged figure.
- **Or measure the per-id part directly**, for example by timing the scope resolution in-process,
  so the fixed costs are not in the ratio.

**Related.** `KI-BO-20261023-gate-verdicts-sensitive-to-machine-load` and
`KI-BO-20261023-uxp-700d-3-i-scan-timeout-flake` are other time budgets that read machine load as
a failure.

**Pattern:** a scaling claim tested with one wall-clock sample per side, where fixed costs dwarf
the part that scales.
