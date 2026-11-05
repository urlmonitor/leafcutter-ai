---
title: "KI-BO-20261023-uxp-700d-3-i-scan-timeout-flake — a UXP-700d-3-i test runs the whole-store AC scan in a subprocess under a 30 s timeout, and on CI shard 7 it timed out on three unrelated PRs in two days"
description: "medium — unit_tests/product_truth/test_uxp_700d_3_i.py::TestSetAsideCountUnchangedByTheRename::test_set_aside_count_matches_independent_recount_after_the_rename runs scripts/ac_store/scan_ac_store.py --json with timeout=30. The scanner loads every YAML file in the AC store (5,320 files on 2026-10-23) and the test then walks the same store again in-process. On CI shard 7/8 the subprocess hit TimeoutExpired on PRs #1305, #1316 and #1320 (runs 39753286415, 39929154081, 39942548263), none of which touched the scanner or the test; a rerun of #1320 passed. The required suite goes red for a reason unrelated to the change under test."
type: reference
category: reference
status: active
created: '2026-10-23'
last_updated: '2026-10-23'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
  - docs/known-issues/testing-quality/resolved/resolved-high-ki-tq-20261021-acs200g-hook-run-outgrows-its-30s-timeout.md
---

# KI-BO-20261023-uxp-700d-3-i-scan-timeout-flake — a whole-store scan under a fixed 30 s timeout

> Filed 2026-10-23. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** medium. Nothing wrong passes: a timeout fails the test. But the failure lands on
  whatever PR is in flight, it fails the required `Test suite (pytest)` check, and each one costs a
  CI rerun and a diagnosis. It also gets likelier as the AC store grows.
- **Status:** open, no AC.
- **Occurrences:** 3 PRs in two days, all on `Test suite shard 7/8`:

  | PR | Run | Date (UTC) |
  |---|---|---|
  | #1305 | 39753286415 | 2026-10-22 |
  | #1316 | 39929154081 | 2026-10-23 |
  | #1320 | 39942548263 (attempt 1; the rerun passed) | 2026-10-23 |

  None of the three PRs touched `scan_ac_store.py`, the test, or the store layout.
- **First seen:** 2026-10-22 · **Last seen:** 2026-10-23
- **Where** (line numbers at `origin/main` `ae3a1591c`):
  - `unit_tests/product_truth/test_uxp_700d_3_i.py`:180-189. The test runs
    `[sys.executable, scan_ac_store.py, "--json"]` with `cwd` at the repo root and `timeout=30`
    (:188). No `--ac-root` is passed, so the scanner reads the real store.
  - `unit_tests/product_truth/test_uxp_700d_3_i.py`:197-211. After the subprocess, the test walks
    the same store again in-process (`sas._walk_ac_yamls(_AC_STORE_ROOT)`, :198) and reloads every
    record to recount.
  - `scripts/ac_store/scan_ac_store.py`:933-946, `main`. It loads every `*.yaml` under the store
    (`_walk_ac_yamls`, :113, an `rglob`) before any filter runs, then builds the id index and
    drains cycles over all records (:949, :954). The work grows with the whole store, not with the
    handful of example ACs the test counts.

## Symptom

The CI log shows:

```
E   subprocess.TimeoutExpired: Command '[... python, .../scripts/ac_store/scan_ac_store.py, '--json']' timed out after 30 seconds
FAILED unit_tests/product_truth/test_uxp_700d_3_i.py::TestSetAsideCountUnchangedByTheRename::test_set_aside_count_matches_independent_recount_after_the_rename
```

The same commit passes on a rerun.

## Mechanism

1. **The budget is fixed; the work is not.** The store had 5,320 YAML files on 2026-10-23 and gains
   files with every authored AC. A 30 s literal was sized against a smaller store.
2. **Shard load decides the outcome.** On a busy shard the YAML parse of the whole store goes
   past 30 s; on a quiet one it does not. Locally, on a Windows dev machine on 2026-10-23, one
   `scan_ac_store.py --json` run took about 70 s.
3. **The test pays for the store twice.** The subprocess loads everything, then the in-process
   recount loads everything again, so the test's total time is about double the scan.

## Detection

A `TimeoutExpired` naming `scan_ac_store.py --json` in this test, on a PR that does not touch the
scanner. Rerun the shard: if it passes, it is this issue.

## Workaround

Rerun the failed CI job. Do not change the PR under review to make it pass.

## Suggested fix

Directions only; nothing here is applied.

- **Scale or raise the budget.** Replace the literal with a budget that scales with the number of
  store files and has an env override, the way `done_proof._resolve_pytest_timeout_seconds` does.
- **Call the scanner in-process.** Call `scan_ac_store.main(["--json"])` with stdout captured, which
  drops interpreter start-up and the timeout, and keeps the "two different ways" comparison (CLI
  entry point vs. the module's own predicates).
- **Narrow what it scans.** Pass `--ac-root` (`scan_ac_store.py` accepts it) pointing at a small
  fixture store that holds the example ACs and a few project ACs. The test then proves the count
  logic without scaling with the real store. If the test must prove the real store's rename is
  complete, keep one in-process recount over the real store and drop the subprocess.

**Related.** `KI-TQ-20261021-acs200g-hook-run-outgrows-its-30s-timeout` (resolved by ACS-200g-3)
was the same defect in another test: a deployed hook run over the whole AC store under a 30 s
timeout. It was fixed by pointing the run at a small fixture store.

**Pattern:** a test with a fixed wall-clock budget that runs against the live, growing repo
corpus.
