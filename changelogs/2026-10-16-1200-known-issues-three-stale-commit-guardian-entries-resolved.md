---
title: "Known issues: three commit-guardian entries whose defects are already fixed on main move to resolved"
date: "2026-10-16"
time: "12:00"
type: manual
components:
  - commit_guardian
summary: "Moves KI-CG-20260909-gate-complexity, KI-CG-20260909-gate-folder-density and KI-CG-20261012-folder-density-conflicts-with-flat-ac-store to docs/known-issues/commit-guardian/resolved/. Each defect was checked against the current source before moving."
description: "KI-CG-20260909-gate-complexity: fixed by GE-131a-2 (51c386618, PR #1110). check-complexity is registered in hooks_manifest and judges each function against its own previous score through _complexity_ratchet.judge_file. KI-CG-20260909-gate-folder-density: fixed by GE-120h-3 (d8cd00a9d, PR #1067). check_folder_density.py reads BEFORE with git ls-tree -r HEAD --name-only, so the blocking branch is reachable. KI-CG-20261012-folder-density-conflicts-with-flat-ac-store: fixed by GE-133a (PR #1168). folder_density.set_aside_locations sets docs/acceptance-criteria/ aside. Each entry gets a Status line naming the fix and the file:line evidence on 496bfecee. The register's Open and Resolved tables are updated and the counts line recounted from the directory: Open 85 (1 blocker, 37 high, 47 low), Resolved 24. The doc_links in GE-131.yaml and GE-133.yaml, and one related_docs entry in resolved-high-ki-cg-20261010, now point at the moved files."
breaking: false
---

## Entry

Three commit-guardian known issues described defects that no longer exist on main. They are now
in `docs/known-issues/commit-guardian/resolved/`:

- `KI-CG-20260909-gate-complexity`: resolved by GE-131a-2, PR #1110.
- `KI-CG-20260909-gate-folder-density`: resolved by GE-120h-3, PR #1067.
- `KI-CG-20261012-folder-density-conflicts-with-flat-ac-store`: resolved by GE-133a, PR #1168.
