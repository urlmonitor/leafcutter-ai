---
title: "The hold check's requirements now say it is published by the repository's own App"
date: "2026-10-09"
time: "17:30"
type: manual
components: 
  - testing_quality
summary: "The requirements for the Post-merge suite status check are amended so a pull request can no longer satisfy it by adding its own job with the same name: the result will be published by a dedicated GitHub App whose key only the main branch can reach."
description: "Required checks on this repository are matched by name and by source, and every GitHub Actions job counts as the same source, so a pull request could add its own job named Post-merge suite status that simply passes. At the owner's direction the hold check's requirements now say its result is published by the repository's dedicated hold App, the Actions job that computes the verdict gets a different name, and the required check is pinned to that App rather than to GitHub Actions. Every failure along the way - a key that cannot be read, a write that fails, a crash - leaves the check not green. The App's key is kept in an environment only the main branch can use, so a workflow added by a pull request cannot read it. The ruleset change still waits until the App has been seen posting the check on real pull requests and a same-named fake has been seen failing to satisfy it. Four requirements are amended and return to review for approval before they are built."
---

## Entry
