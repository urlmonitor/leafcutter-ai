---
title: "check-folder-density refuses merge commits for folders that grew dense on the merged-in branch"
status: todo
components:
  - commit_guardian
created: 2026-10-10
last_updated: 2026-10-10
depends_on: []
priority: high
roadmap_phase: phase_1
change_target: infrastructure
risk_surface: internal
requires_diagram: false
requires_adr: false
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# check-folder-density refuses merge commits for folders that grew dense on the merged-in branch

## Actor / Goal
In order for a branch to take in main without a hook skip, the folder-density hook must treat folders that are already dense on the merged-in branch as pre-existing.

## Context
- **Found:** 2026-10-10. Merging `origin/main` into `docs/pol-git-001` (#990, 492 commits behind) and `acs/decision-lifecycle` (#1004, 377 behind) was refused for 30 and 7 folders respectively, none touched by either PR (e.g. `unit_tests/suite_performance/` 74 files, the DK-200..DK-500 AC folders, `kernel/`, `scripts/ci/`). Both merges needed a user-run `SKIP=check-folder-density` commit.
- **Cause:** `templates/scripts/commit_guardian/check_folder_density.py` reads the BEFORE snapshot from `git ls-tree -r HEAD` only. In a merge, HEAD is the branch's old tip, so every folder that crossed the limit on main since the branch point counts as "newly dense in this commit". Armed to refuse on 2026-10-08 (`d8cd00a9d`, GE-120h-3).

## Scope
1. When `MERGE_HEAD` exists, a folder counts as pre-existing when it is already over the limit in HEAD **or** in MERGE_HEAD (each parent's tree); only a folder the merge result itself pushes over the limit is a violation.
2. Tests: a merge bringing in an already-dense folder passes; a merge that makes a folder newly dense in neither parent but dense in the result is refused; a normal commit is unchanged.
3. Mirror `templates/` → `scripts/` through the build.

## Out of Scope
- Changing the limit or the exemptions.

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
