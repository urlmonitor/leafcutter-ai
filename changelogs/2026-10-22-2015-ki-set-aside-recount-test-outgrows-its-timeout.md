---
title: "Known issue: the set-aside recount test outgrows its 30-second timeout on loaded CI runners"
date: "2026-10-22"
time: "20:15"
type: manual
components:
  - ux_prototyping
summary: "KI-UXP-20261022 records that test_uxp_700d_3_i runs a whole-store scan under a 30-second subprocess timeout and fails intermittently on loaded CI runners; a rerun passes."
description: "Seen on two of three shard-7 runs of PR #1246. Warm local timing is 44 s on main and 47 s on the branch, so this is runner load against a tight limit, not a regression. The fix direction is a larger timeout or a fixture-sized store."
breaking: false
---

## Entry
