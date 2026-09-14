---
title: A decision now governs what a build may remove from a project it shares with its adopter
date: "2026-09-08"
time: "15:32"
type: manual
components: 
  - build_pipeline
  - infrastructure
summary: "Recorded an architecture decision (no behaviour change yet) that will stop the build from deleting an adopter's own work when it installs into their project."
description: "Adds ADR-041, registered in the ADR index and doc index (docs/architecture/adrs/README.md, docs/INDEX.md). No code changes in this PR. The ADR decides what an ordinary build run may remove from an installed tree it shares with the adopter, addressing the currently-open, high-severity defect KI-BP-009 (a no-flag build can destroy adopter-authored content). It sets three rules for the eventual fix: ownership is recomputed on every run from the current template set rather than read off a maintained path list; removal is decided per item, never for a whole shared directory at once; and the build reconciles what it plans to remove against what it plans to claim on every run, refusing rather than resolving a contradiction silently. It also records that install_shims' force parameter defaults to True, so today's non-destructive behaviour is a property of build.py's call site, not the function. Status is Proposed; it serves acceptance criteria BP-1500g and its children."
adrs: 
  - ADR-041
commits: 
  - 39ae2ba7f5a9c5e81085210586d71f395eaad84b
breaking: false
---

## Entry
