---
title: "Changelog 5268230cb — the merge sync job is tested by running it, and its result names its own run"
date: "2026-11-16"
time: "11:25"
type: manual
components: 
  - knowledge_management
summary: "The merge-triggered knowledge sync is now proved by tests that run the workflow's own sync line, and its result carries the merge job's run, commit and generation."
description: "One commit (5268230cb, feat). tests/knowledge/test_km_400e_5.py runs the merge workflow's own sync line through main() for repeated, out-of-order and missed merge events: a repeat publishes the same generation, an older revision is refused by the ancestry guard (exit 2) and the pointer stays put, the declared retention bound reclaims within the same publication and the result reports reclaimed and retained counts, and no credential reaches any output. knowledge/merge_correlation.py adds a correlation block (runner run id and attempt, repository, commit, generation, no retrieval request id, no credential) to the sync result. The unset-setting clause stays proved by test_km_400e_8.py and the lag by test_source_boundaries.py. KM-400e-5 is marked done."
adrs: []
commits: 
  - 5268230cb
breaking: false
---

## Entry
