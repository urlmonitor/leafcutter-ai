---
title: CI test shards are balanced by measured time instead of test count
date: "2026-10-06"
time: "00:15"
type: manual
components: 
  - testing_quality
  - build_pipeline
summary: "The eight parallel test jobs now divide the work by how long each test actually takes, rather than by how many tests there are. The slowest job drops from about forty minutes to about fourteen, because an even count of tests was never an even amount of work."
description: "Adds .github/test_durations.json, 9559 per-test timings totalling 6752s measured on a real CI runner by the test-durations workflow. Until now ci.yml's test-shard matrix had no durations file, so pytest-split fell back to splitting by test COUNT. That gave each of the eight shards an almost perfectly even 1185-1194 tests and a wildly uneven 2m21s to 40m35s of work -- a 17.2x spread -- and the matrix waits for its slowest member, so wall clock sat near 40 minutes against a 53-minute single-job baseline. Greedy longest-processing-time packing over the measured file, which is what pytest-split's duration_based_chunks approximates, projects all eight shards at 14.1 minutes with a 1.00x spread: a 2.9x improvement in wall clock from a data file alone, with no test changed and no coverage lost. The measurement also corrects the earlier local profiling this programme was steering by: tests under tests/knowledge/ appear at 90.7s and 91.5s in the top three, and they contributed exactly zero to every local ranking because five pinned dependencies are absent from a typical developer environment, so 163 modules fail to import locally and run only on CI. The run recorded 9559 of 9559 collected and reported zero shallow-clone fixture errors, confirming the fetch-depth fix shipped alongside it. Two observations recorded rather than acted on here: the longest single test is 120.4s, which is the hard floor no shard count can go below, and the unsharded run reported 26 failures where the sharded run reported 14, which points at order-dependent tests and is tracked separately."
---

## Entry
