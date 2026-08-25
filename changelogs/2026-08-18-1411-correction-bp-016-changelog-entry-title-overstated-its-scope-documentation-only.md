---
title: "Correction: BP-016 changelog entry title overstated its scope (documentation only)"
date: "2026-08-18"
time: "14:11"
type: manual
components: 
  - build_pipeline
summary: "Corrected a misleading changelog entry title that a customer read as claiming the absolute-path symlink bug was fully resolved, when only the git-tracking half of it had been."
description: "Documentation-only correction, no code change. The 2026-08-14 BP-016 changelog entry title (\"Untrack build-shim symlinks committed with absolute local paths\") named the absolute-path hazard while describing a fix to git tracking only; install_shims() kept generating absolute symlink targets until BP-017 (PR #477, 967f37fbc) fixed generation four days later. Added an explicit Correction section to the original entry body (no existing text altered or removed) clarifying what BP-016 fixed (tracking, complete for this repo), what it left open (generation, exposing consumers who vendor build output), and pointing to the BP-017 entry that closed the gap."
adrs: 
  - ADR-016
tickets: 
  - BP-016
breaking: false
---

## Entry
