---
title: "The post-merge hold says plainly when its verdict is stale, its workflow is disabled, or it has never run"
date: "2026-10-12"
time: "13:00"
type: manual
components: 
  - testing_quality
summary: "Each of the hold's six held states now has its own headline, says the pull request did not cause it, and says how to restore a verdict, in both the check output and the pull-request comment."
description: "The Post-merge suite status check already held pull requests when its verdict was stale, the workflow was disabled or no run had ever completed. Each of its six held states - not green, did not finish, stale, disabled, never run, and could not read - now has its own headline, says it is not caused by the pull request, and ends with how to restore a verdict: fix main or declare a proven fix, re-run the suite, dispatch the correctness workflow, re-enable it, wait for the first run, or re-run the check once the history can be read. The pull-request comment now carries the same restore line. A stale verdict names the run's start time and its age to one decimal place, and \"no settled run in the latest page\" counts as stale. An invalid post_merge_tunables.json - a staleness bound not above the heartbeat interval, or a non-numeric value - holds every pull request with \"Post-merge hold configuration is invalid\", naming the file, both keys and their values. docs/testing/README.md gains a lookup table of these messages."
---

## Entry
