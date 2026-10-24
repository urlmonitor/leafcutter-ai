---
title: "KI-ACS-20261023-whole-store-scans-under-30s-hang-guards — tests that run a whole-store AC tool in a subprocess cap it at 30 s, the scan now takes ~22 s warm, and a cold CI shard tips it over, so an unrelated PR fails the required pytest check"
description: "high — several tests run scan_ac_store.py, check_ac_schema.py or validate_ac_schema.py over the real AC store in a subprocess with timeout=30. A whole-store scan measured 21.7 s locally on 2026-10-23 (≈4,600 records) and the store grows daily. On CI, whether a test runs warm or cold depends on the shard split, which any added test file changes, so the timeout fires on PRs whose diff never touches the store tooling: PR #1288 (test_acs200g, twice) and PR #1335 (test_uxp_700d_3_i, twice). Each was fixed one test at a time."
type: reference
category: reference
status: active
created: '2026-10-23'
last_updated: '2026-10-23'
components:
  - ac_store
  - testing_quality
related_docs:
  - docs/known-issues/ac-store.md
  - docs/known-issues/README.md
---

# KI-ACS-20261023-whole-store-scans-under-30s-hang-guards — whole-store scans under 30 s hang guards

> Filed 2026-10-23. Index: [ac-store.md](../ac-store.md).
> Filename severity is the three-level index bucket (`high`); the original grading is the
> `**Severity:**` line below.

- **Severity:** high. Nothing is wrongly accepted, but the required `Test suite (pytest)` check
  fails on PRs that did not cause it, and a re-run does not clear it once the shard split runs
  the test cold.
- **Status:** open. Two instances fixed one test at a time; the class is not fixed.
- **Occurrences:** 4 CI failures across 2 PRs on 2026-10-23.
  - PR #1288: `test_acs200g_pr_scoped_ac_check::test_check_reachable_via_real_entry_point_blocks_on_a_malformed_record`, `check_ac_schema.py` timed out at 30 s, twice. Fixed on main in `5f31a0463` (ACS-200g-3) by moving that test to a fixture repository.
  - PR #1335: `test_uxp_700d_3_i::test_set_aside_count_matches_independent_recount_after_the_rename`, `scan_ac_store.py --json` timed out at 30 s, twice (`1 failed, 1445 passed` both runs). Main was green on the same test because its shard split ran it warm.
- **First seen:** 2026-10-23 · **Last seen:** 2026-10-23

## Measured

- `scan_ac_store.py --json` over the real store: **21.7 s** locally (2026-10-23, warm host cache).
- `check_ac_schema.py` with the repository as root: **15.6 s** warm, **4:06** cold (2026-10-22;
  12.1 s of the warm run is the whole-store index in `get_ac_index`).

## Mechanism

1. The test runs a whole-store tool in a subprocess over the real store, and caps it at 30 s.
2. The tool's cost grows with the store, and the store grows every day.
3. Whether an earlier test in the same CI shard has warmed the store's caches depends on how
   tests are split across shards. Adding any test file anywhere can change the split.
4. So a PR whose diff never touches the store tooling can move such a test into a cold slot,
   and it times out.

## Detection

`grep -rn "timeout=30" unit_tests/` and check each hit against the tool it runs. A hit that
runs `scan_ac_store`, `check_ac_schema` or `validate_ac_schema` over the real store, not a
fixture, is in this class.

## Remedy

Per test, choose by purpose:

- **The test checks behaviour** (e.g. "a malformed record is blocked"): run the tool against a
  small fixture store, as ACS-200g-3 did. Fast and deterministic.
- **The test checks the real store** (e.g. an independent recount, as UXP-700d-3-i does): the
  timeout is a hang guard, not a speed budget. Give it headroom that does not shrink as the
  store grows (UXP-700d-3-i now uses 300 s, PR #1335), and say so in a comment.

Class fix, not done here: sweep every hit of the detection grep and classify each one, and
consider a lint that refuses `timeout=30` on a subprocess running a whole-store tool against
the repository root.

**Pattern:** a test-time budget sized when the input was small, attached to an input that grows.
