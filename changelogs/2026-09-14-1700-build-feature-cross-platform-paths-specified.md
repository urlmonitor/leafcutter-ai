---
title: "Why /build-feature built nothing on Windows is now specified, ready for the fix"
date: "2026-09-14"
time: "17:00"
type: manual
components: 
  - build_orchestration
summary: "Two approved acceptance-criteria trees specify the fix for /build-feature on Windows: paths must work on Windows and POSIX alike, and the worktree step must never nest a worktree."
description: "A /build-feature run on Windows on 2026-09-14 spent about 975k subagent tokens and built nothing. Its path helper read C:\\ paths as relative and joined them onto the worktree, and its worktree step created a second worktree inside the epic's ticket folder. BO-3900 (with BO-3900a to BO-3900d) requires the build workflows' path handling to give the same answer on Windows and POSIX. It covers drive letters, backslashes, mixed separators and whole-segment containment, and refuses path forms it cannot classify one ticket at a time. It is proven for build-feature, plan-feature and build-epic through the Node workflow harness, and by a unit test that feeds Windows-shaped paths on the Linux CI runner and scans every workflow script for POSIX-only absolute-path checks. BO-4000 (with BO-4000a to BO-4000c) requires the worktree step to use the worktree the run already resolved, to name any new worktree's location deterministically outside the target folder, and to stop rather than silently reuse a branch that has fallen behind main. All nine were decided with the user and approved; the code fix follows. The known-issue entries for this incident are held back: check-doc-length now refuses any growth to a register already over its limit, so the registers must be split before new entries can land."
commits: 
breaking: false
---

## Entry
