---
title: "Test timings re-measured, confirming the cheaper build landed and rebalancing the shards"
date: "2026-10-06"
time: "16:58"
type: manual
components: 
  - testing_quality
summary: "The map of how long each test takes was measured again over a full run and replaced. The shards that split the test suite across eight parallel machines are balanced from this map, so a stale one leaves some machines idle while others run long."
description: "Replaces .github/test_durations.json with a fresh full-suite measurement taken on main at 2026-10-06 16:58, superseding the map recorded before the directed shared-layout build and the sharded CI topology merged. Total measured time falls from 6752s to 6432s across 9568 test node ids, nine of them new and none removed. The fall is not uniform and the detail is the point: seventeen tests got at least fifteen seconds faster and not one got slower, and every one of them belongs to the suite-performance family that consumes the shared deployed layout, which is the family the directed build was expected to help. The integration file for that layout's comparison check drops from 261.6s to 86.8s, a threefold cut; the main shared-layout file from 162.8s to 83.2s; the multi-worker file from 82.7s to 29.8s. Those savings total roughly 456s and are partly offset by a new build guard, test_build_leaves_tracked_files_clean.py, which arrived between the two measurements carrying 130.3s across four tests. The files that spawn their own build rather than reusing the shared layout are unchanged, which identifies them as the remaining candidates for the same treatment. The refreshed map also improves shard balance on its own terms, because the superseded map predated nine current tests and could not place them by measured cost."
---

## Entry
