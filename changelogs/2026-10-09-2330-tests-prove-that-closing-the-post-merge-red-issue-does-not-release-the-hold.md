---
title: "Tests prove that closing the post-merge-red issue does not release the hold"
date: "2026-10-09"
time: "23:30"
type: manual
components: 
  - testing_quality
summary: "New tests pin that closing the post-merge-red issue, by hand or through a merged \"Fixes #N\", neither releases the pull-request hold nor resets the list of commits to search, and that the issue comes back on the next red run."
description: "Agents write \"Fixes #N\" by habit, and GitHub closes the referenced issue when such a pull request merges. Tests now show that closing the post-merge-red issue this way, or by hand, changes nothing that matters: pull requests stay held until a post-merge run on main is green, the next red run reopens or recreates the issue, and its commit list still starts at the last green run, so a culprit merged before the close is still listed. When the next run is green, the closed issue is left alone and the hold lifts. A pull request that declares the closed issue as its fix is still held and is told the issue is not open. No behaviour changed; this pins what the hold and the notice already do."
---

## Entry
