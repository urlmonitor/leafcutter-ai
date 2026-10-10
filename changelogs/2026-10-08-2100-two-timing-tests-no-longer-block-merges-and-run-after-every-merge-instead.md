---
title: Two timing tests no longer block merges and run after every merge instead
date: "2026-10-08"
time: "21:00"
type: manual
components: 
  - testing_quality
summary: "Two tests that compare how fast the store parser runs against a slower baseline now run in their own timing suite after every merge, rather than in the required check that every pull request must pass."
description: "The required test check could fail on any pull request just because a shared build machine happened to be slow, since two tests compare one measured duration against another. Those two tests are now tagged as timing tests and left out of the required run, which also saves about 44 seconds per run. A new Post-merge timing suite runs them after every merge to main, every 12 hours, and on demand. It turns red when a timing test fails, and also when it finds no tests to run, so it cannot silently go green. It never blocks a merge. The partition check for opt-in tests now counts the timing tests as their own group, and the testing guides explain how to run them locally."
---

## Entry
