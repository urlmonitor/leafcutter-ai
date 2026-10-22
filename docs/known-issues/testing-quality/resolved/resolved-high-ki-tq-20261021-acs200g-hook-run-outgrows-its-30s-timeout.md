---
title: "KI-TQ-20261021-acs200g-hook-run-outgrows-its-30s-timeout — the ACS-200g reachability test runs the deployed check_ac_schema.py with a hard 30 s subprocess timeout, but one staged file still makes the hook index the whole AC store, so on a cold CI runner the run takes about 25-30 s and times out at random"
description: "high — test_check_reachable_via_real_entry_point_blocks_on_a_malformed_record stages one temp record through HOOK_TEST_STAGED_FILES, but sets HOOK_ROOT to the real repo. check_ac_schema.py main() then builds the full-store cross-file index (5,260 YAML files on 2026-10-21) before it validates the one record. A fresh CI checkout has no on-disk index cache, so the full parse runs every time. The committed durations file records 25.2 s for this one test against its 30 s budget. It failed shard 3/8 in 4 of the last 6 main runs, and it fails the required Test suite (pytest) aggregate. The store grows each week, so the failure rate will rise until the run always times out."
type: reference
category: reference
status: active
created: '2026-10-21'
last_updated: '2026-10-21'
components:
  - testing_quality
  - ac_store
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
  - docs/known-issues/testing-quality/open-low-ki-tq-013.md
  - docs/known-issues/testing-quality/resolved/resolved-high-ki-tq-20260901-1310.md
---

# KI-TQ-20261021-acs200g-hook-run-outgrows-its-30s-timeout — a one-record hook run indexes the whole store and outgrows a fixed 30 s timeout

> Filed 2026-10-21. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`high`); the original grading is the
> `**Severity:**` line below.

- **Severity:** high. The failure is loud, so nothing passes wrongly. The cost is that shard 3/8
  goes red at random, which fails the required `Test suite (pytest)` aggregate. Any PR is then
  blocked until someone reruns it, and the red run is not caused by the change under review. The
  margin shrinks as the AC store grows, so this **escalates to `blocker`** once the run always
  times out.
- **Status:** **RESOLVED 2026-10-21** by ACS-200g-3 (test-only): the reachability test now runs the deployed check_ac_schema.py against a git-initialised tmp fixture repo (3 valid records + ZZTEST-999); each hook run takes ~0.5 s, and new tests prove the hook read only the fixture and left the real tree and real index cache untouched. Tests: unit_tests/build_guards/test_acs200g_pr_scoped_ac_check.py, helpers in _acs200g_fixture.py.
- **Occurrences:** on 2026-10-21, 4 of the last 6 `ci.yml` runs on main failed shard 3/8 with this
  test: runs `39597899863`, `39592669070`, `39577397350` and `39492393948`. On PR #1280 it failed
  twice and passed on rerun.
- **First seen:** 2026-10-21 · **Last seen:** 2026-10-21
- **Where:**
  - The test is
    `unit_tests/build_guards/test_acs200g_pr_scoped_ac_check.py::TestAcs200gPrScopedAcCheck::test_check_reachable_via_real_entry_point_blocks_on_a_malformed_record`
    (:86-135). The `subprocess.run(..., timeout=30)` call is at :120-127.
  - The hook is `.leafcutter/scripts/commit_guardian/check_ac_schema.py`, `main()` at :660-730
    (identical to `scripts/commit_guardian/check_ac_schema.py`). The full-store index is built at
    :686-694.

## Symptom

```
subprocess.TimeoutExpired: Command '[<python>, .../.leafcutter/scripts/commit_guardian/check_ac_schema.py]' timed out after 30 seconds
```

The failure lands on shard 3/8 of the `test-shard` matrix, because that is where pytest-split puts
this test.

## Mechanism

1. **The test scopes the staged set, not the store.** It writes one malformed record
   (`ZZTEST-999.yaml`) to a `TemporaryDirectory` and passes it through `HOOK_TEST_STAGED_FILES`.
   It sets `HOOK_ROOT` to the real repo root and `cwd` to the repo root (:116-123). No fixture
   store is involved.
2. **Any staged file triggers the full-store index.** In `main()`, a non-empty staged set builds
   the cross-file lookup over the whole store, "AC-4: not narrowed" (:686-694). It uses
   `get_ac_index(<root>/docs/acceptance-criteria)`, or the `find_ac_files` walk as a fallback.
   Only after that does it validate the one record. So validating one record costs a parse of all
   5,260 AC YAML files.
3. **CI always pays the cold cost.** `_ac_store_index` keeps its on-disk cache at
   `<git-dir>/ac_store_index_cache.json`. A fresh CI checkout has no such cache, so the first hook
   run on a runner rebuilds the index from YAML. Measured locally on 2026-10-21 in this worktree,
   with the cache deleted: **cold 22.2 s, warm 1.2 s**, exit 1 both times.
4. **The budget is a literal that has not moved.** `timeout=30` is hard-coded in the test. It
   was written with the test on 2026-09-07 (`6732112af`, ACS-200h, #709), when the store held
   3,814 AC files. No shared constant or env override feeds it. The store held 4,768 files when
   `.github/test_durations.json` was last measured (`da1121d29`, 2026-10-07). That file records
   **25.17 s** for this test, which is 84 % of its budget on a normal CI run. The store now holds
   5,260 files, about 10 % more again.

The duration grows with store size, while the budget does not. As the store grows the run sits
closer to the 30 s limit, and a loaded runner pushes it over.

## Detection

A shard failure whose traceback is `subprocess.TimeoutExpired ... check_ac_schema.py ... timed out
after 30 seconds`, raised from `test_acs200g_pr_scoped_ac_check.py`. Check the trend with
`grep acs200g .github/test_durations.json` against `find docs/acceptance-criteria -name '*.yaml' | wc -l`.

## Workaround

Rerun the failed shard. It usually passes, because the runner is less loaded on the second try.

## Suggested fix

- Point `HOOK_ROOT` at a small temp fixture store (schema plus a handful of ACs), so the run no
  longer scales with the real store.
- Or replace the literal with a budget that scales with store size and has an env override, the
  way `done_proof._resolve_pytest_timeout_seconds` does (`KI-TQ-20260901-1310`).

**Related.** `KI-TQ-013` is another random failure of the required suite that comes from the
environment rather than the change under test. `KI-TQ-20260901-1310` (resolved) is the earlier
fixed-budget-against-a-growing-workload defect in `done_proof`.

**Pattern:** a test with a fixed wall-clock budget that runs against the live, growing repo
corpus.
