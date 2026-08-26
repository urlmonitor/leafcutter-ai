---
title: "The self-hosting exit criterion becomes something that can fail (BP-1500)"
date: "2026-08-25"
time: "09:15"
type: manual
components: 
  - build_pipeline
  - roadmap
summary: "Replaced a phase-1 launch checkpoint that could never fail with one that actually tests whether the self-host build tells the truth about what it changed; the underlying problems it checks for are still open and nothing has been fixed yet."
description: "Authors BP-1500 (L0, \"A build does what it says, and says everything it did\") with three L1s — BP-1500a, BP-1500b, BP-1500c — covering KI-BP-001, KI-BP-002, KI-BP-004 and KI-BP-005: the self-host build silently rewrites tracked files, silently overwrites tracked agent cards, reports \"no stale files found\" over a surviving orphan, and leaves deployed gates on an old build without saying so. A new L0 was needed because no existing parent had room: BP-900 is 8/8 on a child_limit_override of 8, BP-900h is 5/5, and BP-100 sits at an override of 13. KI-BP-003 was deliberately left uncovered — it is already discharged three times over by BP-900g-10-iii, BP-900h-4 and BP-900g-8-ii, so authoring against it would have duplicated approved records. A second commit sets all four new ACs from priority: medium to priority: high (PO default vs. user-confirmed severity) and rewords phase_1 exit criterion 4 in docs/roadmap.json (mirrored to docs/roadmap.md) from \"Self-hosting parity: leafcutter development uses its own compiled agents\" — already true today, so it could never gate the phase — to a three-clause criterion that can actually fail: no unrequested edits to tracked files, no orphaned artifacts, no false all-clear. AC store and roadmap only. No production code changed and no defect fixed by this branch — KI-BP-001, KI-BP-002, KI-BP-004 and KI-BP-005 all remain open."
commits: 
  - 6185d334
  - b51e609b
breaking: false
---

## Entry
