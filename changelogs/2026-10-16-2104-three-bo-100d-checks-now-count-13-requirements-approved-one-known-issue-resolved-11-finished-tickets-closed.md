---
title: "Three BO-100d checks now count, 13 requirements approved, one known issue resolved, 11 finished tickets closed"
date: "2026-10-16"
time: "21:04"
type: manual
components: 
  - build_orchestration
  - ac_store
  - ticket_lifecycle
summary: "Three BO-100d checks that were stranded under retired parents now count toward BO-100d, 13 requirements were approved with test plans, the relative-telemetry-path known issue was resolved, and 11 tickets for already-delivered work were closed."
description: "One commit (ac30e839), 31 files changed. BO-100d-1-i, -1-ii and -2-i sat under the retired BO-100d-1 and -2, so done-proof never counted them toward BO-100d; they are retired as superseded and replaced by BO-100d-1a-i, -1a-ii and -2a-i under their live parents, with criteria copied verbatim. 13 ACs (BO-100d-1a, -1b, -2a, -2b, -1a-i, -1a-ii, -2a-i and GE-128a-2, -2-i, -3, -4, -5, -6) moved from draft to approved: code ACs carry a behavioral test_spec, prompt and doc ACs carry a test_rationale. KI-BO-20261009 (BO-100d probe pinned a relative telemetry path) moved to build-orchestration/resolved/ because PR #1262 made the criteria change it asked for; the CLAUDE.md Feedback sink reachable text no longer says the probe ACs pin the relative path. 11 tickets (KM-400f-1-i to -vi, KM-400b-2-i, -2-ii, -5-i, -5-ii, INF-500d-4-ix) went from todo to done after each AC was checked as done with covered_by set; remaining phases on the KM tickets are set to not_needed, not signed_off."
commits: 
  - ac30e839eede7f3d3594e8c6d7d5ac4bdcce6c40
breaking: false
---

## Entry
