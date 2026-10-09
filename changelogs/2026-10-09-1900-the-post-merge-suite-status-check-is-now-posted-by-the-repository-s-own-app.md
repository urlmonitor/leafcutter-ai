---
title: "The Post-merge suite status check is now posted by the repository's own App"
date: "2026-10-09"
time: "19:00"
type: manual
components: 
  - testing_quality
summary: "The hold check's result on a pull request is now published by the dedicated hold App, so a pull request can no longer pass it by adding its own job with the same name once the ruleset is pinned to the App."
description: "The job that works out whether main's post-merge suite is green is now called Post-merge hold evaluation, and the result that a pull request shows as Post-merge suite status is created by the repository's dedicated hold App on the pull request's own head commit. The check is created as in progress before the verdict is worked out and completed afterwards as success only for a pass, failure otherwise, so a crash or an unreachable service leaves it not green. A missing or rejected App key, an uninstalled App, or a refused write each fail the job with a message saying which, without printing the key. The App's key stays inside the signing step, is read from an environment that only the main branch can use, and the short-lived token it produces is limited to writing checks on this repository. The ruleset still requires the old source until the App has been seen posting the check on real pull requests."
---

## Entry
