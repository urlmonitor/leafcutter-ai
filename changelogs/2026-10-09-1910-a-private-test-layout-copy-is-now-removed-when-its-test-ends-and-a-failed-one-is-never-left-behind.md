---
title: "A private test layout copy is now removed when its test ends, and a failed one is never left behind"
date: "2026-10-09"
time: "19:10"
type: manual
components: 
  - testing_quality
summary: "Tests that need their own private copy of the deployed package now clean it up afterwards, so repeated test runs stop filling the disk."
description: "The shared-layout fixture built a 140-200 MB private copy for every undeclared or mutator test and never deleted it, and a failed copy, deploy or completeness check left a half-built one behind. The fixture now removes that private copy when the test finishes, pass or fail, and removes a partial copy before reporting a build failure. A failed cleanup is logged as a warning and never fails the test. The single shared layout used by read-only tests is never removed. Covered by behavioural tests with the build stubbed out (AC TQ-600a-2-i, commit 51ab4c780)."
commits: 
  - 51ab4c780680044930c6d7d408c10eea3b028ed3
breaking: false
---

## Entry
