---
title: "A pre-sweep baseline of every registered check, captured before the resolution sweep touches them"
date: "2026-09-28"
time: "16:40"
type: manual
components:
  - commit_guardian
  - precommit_hooks
  - testing_quality
summary: "Lands the GE-120b-2-i capture apparatus and the recorded pre-sweep baseline: a capture/verify CLI built on the GE-120c-1 harness, a shared provoking fixture, and a per-check verdict record for all 75 manifest checks taken against origin/main 89613071 while GE-120b-2 is still work_status todo. 30 of 75 checks are provoked to a real violation so far; the residual is recorded honestly rather than claimed."
description: "GE-120b-2-i asks whether the shared prerequisite-resolution sweep of GE-120b-2 changes any check's verdict in the main checkout. That question can only be answered against a baseline captured BEFORE the sweep, which the AC states three times and whose coverage note calls a post-hoc baseline the single most likely way the criterion gets faked. GE-120b-2 is still work_status todo, so this commit takes that baseline while the window is open. It adds ge120b2i_verify_unchanged.py with capture and verify subcommands, both built on GE-120c-1's DeployedCheckHarness rather than an implementer-authored apparatus, per the AC's own it_requirements; and _ge120_provoking_fixture.py with a stage(working_copy_dir) entry point, shared with GE-120b-4 which requires the same fixture built once and owned in one place. Every check runs against the DEPLOYED copies inside a fresh second working copy, never templates/, because the deployed layout is what pre-commit actually invokes. The manifest is read at run time and is 75 entries today; it was 62 three weeks ago and 54 when the AC was written, which is why no count is hard-coded anywhere. The recorded baseline covers all 75 by check id, never aggregated, since an aggregate rate would hide the single check going quiet that this AC exists to catch. Of the 75, 30 are provoked to a genuine violation and 45 are not yet. That residual is published rather than papered over: a check that is clean against the fixture could have silently stopped running, so its agreement after the sweep proves nothing, and the fixture needs further work before the after-run is fully informative. Part of the residual is not reachable by any fixture content at all — five manifest hooks ship enabled:false, one declares fail_open, and seven are transform-tier and do not judge — which means the AC's requirement to provoke every registered check cannot be satisfied as literally written and needs an amendment rather than more fixture effort. The four verdict-comparison tests in test_ge_120b_2_i.py remain deliberately RED and that test file remains deferred: they compare a pre-sweep baseline to a post-sweep run, and there is no post-sweep state until GE-120b-2 lands. Only the reachability test passes. No baseline was hand-authored and no test was weakened, skipped or xfailed to manufacture a green."
breaking: false
---

## Entry

### What this is

A recorded, per-check verdict baseline for **all 75** manifest checks, captured by
**execution** against `origin/main` `89613071` while `GE-120b-2` is still `todo`.

| | count |
|---|---|
| provoked to a real `violation` | **30** |
| not yet provoked (`clean`) | **45** |
| total (manifest read at run time) | **75** |

### Why the timing is the whole point

`GE-120b-2-i` can only be answered against a baseline taken **before** the sweep. The AC
says so three times and names a post-hoc baseline as the likeliest way it gets faked. The
window is open exactly until ticket 09 starts.

### The residual is published, not papered over

45 checks are not yet provoked. A check that is **clean** against the fixture could have
silently stopped running, so its agreement after the sweep would prove nothing. Part of
that residual is **unreachable by any fixture**: five hooks ship `enabled: false`, one
declares `fail_open`, and seven are transform-tier and do not judge. The AC's "provoke
every registered check" therefore cannot be met as written and needs an amendment.

### Still RED, deliberately

The four verdict-comparison tests compare a pre-sweep baseline to a post-sweep run. There
is no post-sweep state. `test_ge_120b_2_i.py` stays deferred; only the reachability test
passes. Nothing was hand-authored, weakened, skipped or xfailed to manufacture a green.
