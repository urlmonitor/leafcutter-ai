---
title: "Folder density sets declared stores aside on Windows too, and sets the decision store aside"
date: "2026-10-13"
time: "07:14"
type: manual
components:
  - commit_guardian
summary: "check-folder-density's set-aside locations did nothing on Windows: folder names came out with backslashes and never matched the declared paths, so a crossing in the AC store was still refused. Folder names now use forward slashes on every platform. The decision kernel's record store, docs/decisions/, is now set aside next to the AC store."
description: "GE-133a (PR #1168) lets check-folder-density set aside folders under a location declared in folder_density.set_aside_locations. The check built folder names with str(Path(...).parent), which uses backslashes on Windows, while the declared paths use '/'. On Windows nothing was ever set aside: a commit taking an AC-store folder past 15 files printed '0 folders set aside' and was refused, and the five set-aside tests fail there. Folder names are now built with .as_posix(), and the matching helper also reads backslash separators as '/'. By the user's decision dec-e34583d93c00584f, published here, the shipped declaration also holds docs/decisions/, the decision kernel's flat record store. Its records are written and read by the kernel's publish, index and precedent tools and reviewed in PRs, and the store grows by one file per decision. Both entries carry the grounds GE-133a-1 words, GE-133 is approved, and docs/pre-commit-hooks.md names both stores. New tests cover the backslash matching and the shipped declaration against the deployed check."
commits: [143c579bd, a5e280a4b]
breaking: false
---

## Entry
