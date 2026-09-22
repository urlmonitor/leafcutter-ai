---
title: "An adopter's own files in a shared project now survive an ordinary build"
date: "2026-09-15"
time: "00:07"
type: manual
components: 
  - build_pipeline
summary: "Fixed a defect where running the build tool with no special flags could silently delete an adopter's own files from their project, such as a custom skill they had placed alongside the tool's own files."
description: "Fixes KI-BP-009 (5 commits, ADR-041 already on main): the build now recomputes, per item rather than per directory, whether it produced something before removing it, refuses when it is about to remove and reinstall the same path in the same run, and reports what it keeps because it cannot attribute it. A second review round found the same defect surviving on machines where symlinks are unavailable, because the removal check trusted the configured strategy instead of the method actually used; that is fixed by probing the real behavior on every run. This is the targeted repair for the reported data loss and the platform case found reviewing it, not the general orphan-sweep feature, which remains separate."
adrs: 
  - ADR-041
commits: 
  - 21c5187b42a9b113a6faf8e471b2712ba062d07b
  - 2fc29efb2343ae02b3be5b95b73bcd426674422d
  - 7a3f4c689fcaca3ebe0543455a78ea04a188fcdd
  - b9fb441bd4a77003950966de06e3d78bf68707ab
  - fcfd6a375790e3d8000b631bc49033be019ea458
breaking: false
---

## Entry
