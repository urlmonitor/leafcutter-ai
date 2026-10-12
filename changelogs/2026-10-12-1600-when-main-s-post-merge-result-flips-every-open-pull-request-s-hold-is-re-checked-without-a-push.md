---
title: "When main's post-merge result flips, every open pull request's hold is re-checked without a push"
date: "2026-10-12"
time: "16:00"
type: manual
components: 
  - testing_quality
summary: "A new reevaluate job re-runs the latest Post-merge suite status check of every open pull request whenever main's post-merge verdict changes between green and not green, and names any pull request whose check could not be re-run."
description: "The hold is evaluated on pull-request events, so a pull request kept its earlier result until something evaluated it again: one that passed before main went red stayed mergeable, and one held during a red run stayed held after main recovered until its author pushed. Now, when a post-merge correctness run settles with a verdict different from the previous settled run - green to not green, or back - a reevaluate job in the follow-up workflow re-runs the latest hold check of every open pull request into main. Checks still running are left alone, since they read the new history themselves; a pull request whose check is older than 30 days, whose re-run is refused, or which has no hold check is named on the post-merge-red issue and in the job log. An unchanged verdict, did-not-complete followed by red, or a superseded cancellation re-runs nothing. When a fix-proof run completes, only that pull request's hold is re-run, and only for a pull_request_target proof from this repository. The job's only write is re-running hold checks. Whether the workflow's own token may request those re-runs is still to be observed live; until then a held pull request can be re-run by hand."
---

## Entry
