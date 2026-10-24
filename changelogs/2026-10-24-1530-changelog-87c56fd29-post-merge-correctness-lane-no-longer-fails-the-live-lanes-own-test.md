---
title: "Changelog 87c56fd29 — post-merge correctness lane no longer fails the live lane's own test"
date: "2026-10-24"
time: "15:30"
type: manual
components: 
  - testing_quality
summary: "main's post-merge suite was red because the correctness lane, which starts no database, ran the live lane's real-database test; that test now runs only inside the live-database lane."
description: "Two commits (87c56fd29 fix, 251c0d597 test). The live-database lane (live_run, live_retry) and the fix proof's live session now set POST_MERGE_LIVE_LANE=1 for their own pytest child after their database check (scripts/ci/_live_lane.py, post_merge_suite.py, post_merge_fix_proof.py). tests/knowledge_live/lane/test_tq_600a_13_xxi.py skips without that marker, so the correctness lane, which also selects this `manual` test, no longer fails it on a missing database; inside the live lane an unreachable database is still a failure. New AC TQ-600a-13-xxvii. Main had been red since 2026-10-23T21:37Z (notice #1338), which failed the post-merge hold on every open pull request."
adrs: []
commits: 
  - 87c56fd29
  - 251c0d597
breaking: false
---

## Entry
