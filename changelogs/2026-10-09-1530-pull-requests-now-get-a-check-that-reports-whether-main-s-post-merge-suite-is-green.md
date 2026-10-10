---
title: "Pull requests now get a check that reports whether main's post-merge suite is green"
date: "2026-10-09"
time: "15:30"
type: manual
components: 
  - testing_quality
summary: "A new check named Post-merge suite status runs on every pull request to main and passes only when the latest settled post-merge run on main succeeded within the last 30 hours."
description: "Every pull request to main now gets a check called Post-merge suite status. It reads the post-merge suite's run history on main and passes only when the workflow is active and the latest settled run succeeded less than 30 hours ago. Otherwise it fails and says why: the suite is red, a run did not complete, the last result is stale, the workflow is disabled or has never run, or the history could not be read. It links the post-merge-red notice when that notice describes the same run. Runs that a newer merge cancelled are ignored, and the timing lane never holds a pull request. The check never checks out or runs the pull request's own code: it reads only the default branch's scripts. It is not yet a required check, so it does not block merging until the ruleset is changed in a later step."
---

## Entry
