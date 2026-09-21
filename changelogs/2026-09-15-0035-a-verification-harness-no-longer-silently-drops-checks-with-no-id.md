---
title: A verification harness no longer silently drops checks with no id
date: "2026-09-15"
time: "00:35"
type: manual
components: 
  - testing_quality
summary: "Fixed a bug in a test-verification harness that could make it report more checks exercised than it had actually reached."
description: "1 commit (0247c7101), Bug Fixes. _deployed_check_harness.py's run_sweep() read each manifest hook's id via hook.get(\"id\") and used the untyped result both as a str-declared field and as a dict key; a hook entry with no id became a None-keyed sweep entry no later lookup could reach, and a second id-less entry silently overwrote it. Ids are now validated up front, and a malformed entry is reported through the harness's existing failed_setup_step channel rather than skipped or raised."
commits: 
  - 0247c7101
breaking: false
---

## Entry

`unit_tests/portability/_deployed_check_harness.py`'s `run_sweep()` sweeps the deployed
pre-commit manifest and reports how many of its checks it actually exercised. It read each
hook's id with `hook.get("id")` and used that untyped result both as `CheckSweepEntry.
check_id` (declared `str`) and as the key of the `entries` dict it builds up. A hook entry
with no usable id therefore became a `None`-keyed pseudo-check that no later id-keyed lookup
could reach, and if a second id-less entry turned up it silently overwrote the first — the
sweep could report more checks exercised than it had actually made reachable in its own
result, which is exactly the failure mode this harness exists to catch in everything else.

Caught as a pair of mypy `arg-type`/`index` errors on this file. Fixed by validating each
hook's id up front (`_hook_check_id`) before the sweep loop runs, and routing a malformed
entry through the harness's existing `failed_setup_step` channel — the same one used when a
deployed layout copy is missing — rather than skipping the entry or raising. Validation runs
before the `check_ids` filter and before any subprocess is spawned, so a malformed entry can
no longer be filtered away unnoticed, and refusing costs no wasted work.

No behavior change for a well-formed manifest: the real deployed manifest's 67 hooks all
carry usable ids, so the happy path is unaffected.
