---
title: "feat(code-review): Tiered Parallel Fowler Code-Smell Review"
date: "2026-08-11"
time: "00:00"
type: manual
components: 
  - review_system
  - skills_system
adrs:
  - ADR-032
summary: "Added a code-smell review capability that scans code against Martin Fowler's twelve named smells (Refactoring, 2nd ed) using two parallel specialist agents and merges results into a single severity-ranked report with named removal refactorings and verbatim Before excerpts."
description: "3 new skills: review-for-code-smells (shared core: severity rubric, finding/report format), review-for-structural-code-smells (6 mechanical smells), review-for-design-code-smells (6 judgment smells). 2 new read-only leaf agents: find-structural-smells (Sonnet) and find-design-smells (Opus) — each loads core + its bucket. 1 orchestration skill + /code-smell-review command: top-level fan-out runs both agents in parallel and merges into one severity-ranked report (depth-1 sub-agent limit respected). Retired earlier single-agent find-code-smells. AC tree: docs/acceptance-criteria/code-review/CR-100-refactoring-guidance."
commits: []
breaking: false
---

## Entry
