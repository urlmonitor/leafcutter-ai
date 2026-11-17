---
title: "Stop pull request checks from showing a false failure after merge-check follow-ups"
date: "2026-10-12"
time: "20:00"
type: manual
components: 
  - testing_quality
summary: "Automatic re-runs of the post-merge hold check are now switched off by default, because they made every pull request show a failed hold run even though the check had passed."
description: "When the post-merge follow-up asked GitHub to run a pull request check again, GitHub accepted the request but the new run failed on start-up, so the pull request showed a failure over a check that had actually passed. Re-runs are now opt-in: they only happen when the repository variable POST_MERGE_REEVAL_RERUN is set to true. While it is unset, the follow-up lists the pull requests that need a re-run in the post-merge notice so they can be re-run by hand. The follow-up also no longer re-runs a check after a fix-proof run in which nothing was actually proved."
---

## Entry
