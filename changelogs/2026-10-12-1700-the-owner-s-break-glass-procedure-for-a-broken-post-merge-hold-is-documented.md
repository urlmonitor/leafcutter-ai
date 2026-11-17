---
title: "The owner's break-glass procedure for a broken post-merge hold is documented"
date: "2026-10-12"
time: "17:00"
type: manual
components: 
  - testing_quality
summary: "docs/testing/README.md now holds the owner-only procedure for merging a repair when the Post-merge suite status check itself is broken: remove only that one required check, merge, restore it pinned to the hold App, verify, and log the use."
description: "Once Post-merge suite status becomes a required check, a broken hold - erroring on every pull request, never reporting, unable to publish because the hold App's credential is gone, or holding its own fix - would stop every merge. The testing README now documents the way out, for the repository owner only, with a first line telling agents never to perform it: record the ruleset; remove only the Post-merge suite status entry from the required checks, never adding a bypass actor, because every agent acts as the same admin account; merge the repair; restore the identical entry sourced from the hold App and never from GitHub Actions, which would reopen the check-name spoof; read the ruleset back to confirm the six other required checks are untouched; re-check that a held pull request is reported unmergeable; and log the date, reason, repairing pull request and restore time on the open notice or in the log table beside the procedure. The procedure is to be rehearsed once on the real repository within a day of the check becoming required; that rehearsal has not happened yet."
---

## Entry
