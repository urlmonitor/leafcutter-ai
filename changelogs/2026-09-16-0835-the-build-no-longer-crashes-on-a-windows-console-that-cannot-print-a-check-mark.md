---
title: "The build no longer crashes on a Windows console that cannot print a check mark"
date: "2026-09-16"
time: "08:35"
type: manual
components: 
  - build_pipeline
summary: "On a Windows console using cp1252, build.py died with UnicodeEncodeError right after writing the build manifest, because the success line prints a ✓ that the console encoding cannot represent. Every build status helper now falls back to replacing unprintable characters, so the build finishes and the line reads '?' instead of crashing. UTF-8 consoles are unchanged."
description: "All build status output goes through the print helpers in scripts/build_colors.py (success, warn, error, info, dry_run, heading), and each called print() directly. When stdout's encoding cannot represent a character, print() raises rather than degrading, so the first ✓ after the manifest write killed the run. The same crash also broke worktree bootstrap, where setup_ticket_worktree.py runs build.py. The helpers now route through one private _emit() that retries with errors='replace' in the current stdout encoding. It looks up sys.stdout at call time and nothing happens at import time. Covered by BP-100f-4. A test puts the helpers on a strict cp1252 stream. Reverting the fix turns that test red again. A real build.py run with PYTHONIOENCODING=cp1252 now exits 0."
commits: 
  - 8283debd
breaking: false
---

## Entry
fix(build-pipeline): build output no longer crashes on non-UTF-8 consoles (BP-100f-4)
