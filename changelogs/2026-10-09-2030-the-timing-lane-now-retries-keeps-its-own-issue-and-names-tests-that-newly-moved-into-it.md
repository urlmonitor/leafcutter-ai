---
title: "The timing lane now retries, keeps its own issue, and names tests that newly moved into it"
date: "2026-10-09"
time: "20:30"
type: manual
components: 
  - testing_quality
summary: "The post-merge timing suite now runs, retries failures once on a fresh machine and writes a verdict like the correctness suite, and a red timing run opens its own post-merge-timing issue that never holds pull requests."
description: "The Post-merge timing suite, which runs the wall-clock ratio tests, now has the same run, retry and verdict jobs as the correctness suite, so a timing test that fails once and then passes is recorded rather than turning the run red. A red timing run opens or updates a separate issue labelled post-merge-timing and a green one closes it; the timing lane never touches the post-merge-red issue and never holds a pull request. When a red timing run contains tests that were not in the previous run, the issue names each of them with the commit that touched it, so a test moved out of the holding lane is seen rather than silent. A run in which every test failed is now reported as red with the failing tests listed, instead of as not completed. The testing README now describes both post-merge lanes."
---

## Entry
