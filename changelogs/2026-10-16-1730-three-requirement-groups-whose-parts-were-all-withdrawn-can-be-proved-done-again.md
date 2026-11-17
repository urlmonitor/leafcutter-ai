---
title: Three requirement groups whose parts were all withdrawn can be proved done again
date: "2026-10-16"
time: "17:30"
type: manual
components: 
  - build_orchestration
  - commit_guardian
summary: "Three requirement groups whose parts had all been withdrawn can be proved done again: BO-100d now points at its live successors and probes the install's declared log location instead of a relative path, GE-128a gains draft children for its per-file ratchet, and BO-530-3's retry-cap reference is updated."
description: "One commit (e276e28), 18 AC records edited or added, no work_status changed. BO-100d covered_by now lists BO-100d-1a, -1b, -2a and -2b alongside the retired -1 and -2; those successors and the L3s -1-i, -1-ii and -2-i now probe the absolute path from the install's telemetry location query, and an unusable answer blocks with rebuild rather than falling back to the relative path (KI-BO-20261009-bo100d-probe-pins-a-relative-telemetry-path). Those seven BO-100d ACs moved from approved to draft and await re-approval. BO-530-3 only has one it_requirements line repointed from the retired BO-530-3-i to its ACD-2000a successors. GE-128a gains six new draft children (GE-128a-2, -2-i, -3, -4, -5, -6) for its per-file ratchet; they also await approval. All 18 files pass validate_ac_schema.py."
commits: 
  - e276e28d039c7a83f649612ad3e52d9e232109d6
breaking: false
---

## Entry
