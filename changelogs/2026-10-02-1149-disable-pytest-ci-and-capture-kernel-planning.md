---
title: "Disable the full pytest CI job and capture kernel planning"
date: "2026-10-02"
time: "11:49"
type: maintenance
components:
  - build_pipeline
  - decision_kernel
summary: "Disable the full pytest CI job indefinitely at the owner's request because of its runtime, while retaining the other CI jobs and local commit hooks. Capture the draft kernel feature-planning and knowledge-resolution design."
description: "The pytest job is disabled before runner allocation; its steps remain available for an explicit future re-enable. Remove only Test suite (pytest) from the main-branch required checks. The indexed draft records persona prerequisites, typed context retrieval, uncertainty handling, readiness checks, and unresolved design decisions."
---

## Entry

The full pytest suite no longer runs in GitHub Actions. Other CI jobs and local
commit hooks retain their existing behavior. The matching pytest requirement
is removed from the main-branch ruleset.

The new kernel planning explanation remains a draft design discussion.
