---
title: "KI-UXP-20261022-set-aside-recount-test-outgrows-its-timeout — test_uxp_700d_3_i runs a whole-store scan under a 30-second subprocess timeout and times out on a loaded CI runner"
description: "low — TestSetAsideCountUnchangedByTheRename::test_set_aside_count_matches_independent_recount_after_the_rename calls scripts/ac_store/scan_ac_store.py --json with timeout=30. The scan reads the whole AC store (about 5,300 records). On PR #1246 the shard-7 runner timed it out on two of three runs; a rerun passed. Warm local timing is 44 s on main and 47 s on the branch, so this is runner load against a tight limit, not a regression."
type: reference
category: reference
status: active
created: '2026-10-22'
last_updated: '2026-10-22'
components:
  - ux_prototyping
related_docs:
  - docs/known-issues/ux-prototyping.md
  - docs/known-issues/README.md
---

# KI-UXP-20261022-set-aside-recount-test-outgrows-its-timeout — a whole-store scan under a 30-second limit

> Filed 2026-10-22 from PR #1246 (EPIC-RightJobRightAgentFollowUps). Index: [ux-prototyping.md](../ux-prototyping.md).

- **Severity:** low. The required pytest check fails intermittently. That blocks merges until someone
  reruns the shard; nothing in the product is wrong.
- **Status:** open, no AC.
- **Occurrences:** 2 (PR #1246, shard 7/8, runs at f10a7bf2d and 78a645548) · **First seen:** 2026-10-22 ·
  **Last seen:** 2026-10-22
- **Where:** `unit_tests/product_truth/test_uxp_700d_3_i.py`, about line 188 (`timeout=30` on the
  `scan_ac_store.py --json` subprocess).

## What happens

The test re-counts the set-aside records independently, then compares that number with the
scanner's own count. The scanner reads every record in the store. On a CI shard that ran for 52
minutes, the scan passed 30 seconds and raised `subprocess.TimeoutExpired`. A rerun of the same
commit passed.

The branch did not make the scan slower: warm local runs measure 44 s on origin/main and 47 s on
the branch. The limit is simply close to the scan's real cost on a busy runner. This is the same
pattern as the acs200g reachability-test timeout recorded on main on 2026-10-21.

## Fix direction

Raise the subprocess timeout to a value with real margin for a whole-store scan, or scan a
fixture-sized store when the test only needs the count logic.
