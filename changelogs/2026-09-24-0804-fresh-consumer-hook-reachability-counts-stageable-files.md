---
title: "Fresh consumer installs count stageable build outputs in hook reachability"
date: "2026-09-24"
time: "08:04"
type: manual
components:
  - build_pipeline
  - commit_guardian
summary: "The hook-trigger reachability check now counts existing, unignored files that Git can stage, not only files already in the index. This lets a newly built consumer project commit its Leafcutter bootstrap without treating generated documentation and hook files as unreachable locations. Ignored-only paths and malformed hook definitions remain blocking."
description: "AC BP-100k-4-iii covers the fresh-consumer boundary left open by BP-100k-4-ii. The one-file production change uses git ls-files --cached --others --exclude-standard. A new behavioral test exercises untracked stageable files, ignored-only files, invalid registry entries, and a real build.py consumer layout. An existing kind-based test fixture was updated to ignore generated Python files so its no-stageable-Python premise remains true. The new regression failed before the code change, passed afterward, failed again when the old enumeration was temporarily restored, and passed again after restoration. The real Youtube-Summarizer bootstrap produced unreachable=0. On Windows, the surrounding suite passed 30 tests with one pre-existing POSIX-only regex-timeout test deselected; its SIGALRM guard is unavailable on Windows."
commits:
breaking: false
---

## Entry

Leafcutter's first commit in a consumer project was blocked because the reachability
check looked only at already-tracked paths. `build.py` had created files under `docs/`,
`scripts/`, and other hook locations, but none counted until the first commit—the
commit the check prevented. The check now includes those existing, unignored files
that Git could stage. It still refuses hooks whose only matching paths are ignored,
invalid regexes, and whole-tree hooks carrying a contradictory file filter.
