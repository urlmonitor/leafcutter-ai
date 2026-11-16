---
title: "Changelog fccaeded8 — KM-400b gets a covering test and is closed"
date: "2026-11-16"
time: "10:31"
type: manual
components: 
  - knowledge_management
summary: "KM-400b, keeping answers tied to a dependable project version, is closed: a new end-to-end test follows one repository through publish, a failed update, the next good update and a rebuild."
description: "One commit (fccaeded8, test). tests/knowledge/test_km_400b.py runs the real sync over real Git commits with only the Neo4j driver replaced, and checks that a published version is identifiable, that a failed update leaves it usable and removes only what it wrote, that the next update (a real child commit, so the real descendant check runs) becomes the new identifiable version with the old one intact, and that the repository rebuilds into an empty store with the same identities. Skipping the count check or leaving the failed update's data behind each turns it red. KM-400b is marked done with the test in covered_by; its children were already done, and the untagged-done ratchet stays at its mark."
adrs: []
commits: 
  - fccaeded8
breaking: false
---

## Entry
