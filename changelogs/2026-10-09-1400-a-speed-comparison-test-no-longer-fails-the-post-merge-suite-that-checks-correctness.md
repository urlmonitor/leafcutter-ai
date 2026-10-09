---
title: "A speed-comparison test no longer fails the post-merge suite that checks correctness"
date: "2026-10-09"
time: "14:00"
type: manual
components: 
  - testing_quality
summary: "The one test that compares how long a build-heavy group of tests takes before and after a speed-up now runs in the timing lane, which reports but never blocks, instead of the post-merge suite that decides whether main is healthy."
description: "The post-merge suite on main went red on its first two runs because of a single test: the one that times a group of tests with and without the shared-build speed-up and requires the faster run to take at most two thirds as long. How long that takes depends on how busy the machine is, so it failed on two different machines even though nothing was broken. That test is now marked as a timing comparison, so the correctness run no longer picks it up and the timing lane (which reports its result and never holds anything up) runs it instead. It still stays out of the ordinary default run, as before. The check that every test is run by exactly one lane was updated to say so: ordinary tests, slow opt-in tests without a timing comparison, and timing comparisons are three separate groups that together cover the whole suite. No other opt-in test compares two measured durations, so no other test changed."
---

## Entry
