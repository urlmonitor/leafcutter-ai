---
title: "Changelog 7026063f8 — completion routing claim-store lock works on Windows"
date: "2026-10-25"
time: "00:40"
type: manual
components: 
  - infrastructure
summary: "The completion routing step now works on Windows as well as Linux and macOS, so claims load and are arbitrated on both."
description: "One commit (7026063f8, fix). completion_routing.py no longer imports the POSIX-only fcntl at module level; it takes the exclusive lock through fcntl.flock on POSIX and msvcrt.locking on Windows, imported per platform, and a platform with neither still raises instead of skipping the lock. Same approach as scripts/suite_performance/_shared_layout_coordination.py. AC INF-700a-5-iv."
commits: 
  - 7026063f8
breaking: false
---

## Entry
