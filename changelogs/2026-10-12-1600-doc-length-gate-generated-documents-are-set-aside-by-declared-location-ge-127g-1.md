---
title: "Doc-length gate: generated documents are set aside by declared location (GE-127g-1)"
date: "2026-10-12"
time: "16:00"
type: manual
components: 
  - commit_guardian
summary: "The document-length check no longer holds machine-generated documents to the limit written for hand-authored ones, but this is only part of the feature and set-aside locations are currently unbounded."
description: "Replaces doc_length.excluded_files (basename list) with doc_length.set_aside_locations, a list of {path, ground} objects; an entry with no ground is rejected. Three locations are declared, each regenerated whole with no human author: docs/agents/cards/, docs/roadmap.md, docs/INDEX.md. A path ending / matches everything beneath it at any depth; anything else matches one document exactly; basename plays no part, so a newly generated document joins with no edit to the declaration (a test asserts this). SCOPE: this delivers GE-127g-1 and GE-127g-1-i only, two of five children of GE-127g, which stays todo. Reporting what was set aside (GE-127g-2) and the per-location ceiling (GE-127g-5) are NOT delivered, so a set-aside location is currently unbounded: exempt from the limit with nothing yet capping its growth. WIDENING: the old basename match exempted every README.md and CHANGELOG.md anywhere under docs/; that is gone, so hand-authored READMEs are back in scope. Two are already over the 300-line limit and grandfathered by the growth ratchet, so nothing fails today but they may not grow again. This is intended. DEAD CONFIG KEY: nothing reads excluded_files any more and nothing warns about it, and its default changed from [README.md, CHANGELOG.md] to []. A config still carrying that key has a silently inert setting and its documents return to scope with no message naming the cause. A warning was deliberately not added; it is new behaviour needing its own criterion. Not breaking: commit_guardian.json is a build output that build.py overwrites, so there is no hand migration. Commits: 49339b98c (implementation) and a1f816328 (AC-store reconciliation). A third change fixing two stale comments is staged but not yet committed, so it has no sha and is not listed."
commits: 
  - 49339b98c
  - a1f816328
breaking: false
---

## Entry
