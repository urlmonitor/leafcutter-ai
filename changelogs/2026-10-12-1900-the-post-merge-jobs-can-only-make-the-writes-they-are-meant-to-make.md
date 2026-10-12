---
title: "The post-merge jobs can only make the writes they are meant to make"
date: "2026-10-12"
time: "19:00"
type: manual
components: 
  - testing_quality
summary: "The shared GitHub client used by the post-merge suite, notices, re-evaluation, fix proof and hold now refuses, before sending, every write outside a short allowlist, and tests prove no path changes the repository's code."
description: "The post-merge jobs exist to catch silent corruption, so they must never try to fix anything themselves. Every client is now created with a write policy and is read-only by default; any other write is refused before it is sent. The allowed writes are: creating, editing, commenting on, labelling (a notice the job itself created) and closing issues labelled post-merge-red, post-merge-timing or post-merge-flaky, and never a pull request that carries such a label; the hold's own marked comment on the pull request it is evaluating, after reading the comment to confirm it is the hold's; re-running a pull_request_target run of the hold workflow in this repository; and, with the hold App's token only, creating and completing the check run named Post-merge suite status on the evaluated pull request's head commit, without changing its name or commit. Every write must target this repository. Tests run every path against a recording service and a real scratch repository with a local origin, check that only allowed writes happen and that branches, tags and files are unchanged, and confirm that adding a step which pushes, opens a pull request, edits a file, or dispatches, disables or re-runs another workflow is caught. Each job's workflow permissions are also checked to be exactly the minimum."
---

## Entry
