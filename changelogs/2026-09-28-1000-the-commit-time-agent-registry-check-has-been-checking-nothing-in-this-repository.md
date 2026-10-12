---
title: "The commit-time agent-registry check has been checking nothing in this repository"
date: "2026-09-28"
time: "10:00"
type: manual
components: 
  - commit_guardian
summary: "A new known issue records that check-agent-registry looks for a leafcutter/ folder this repository does not have and passes having validated nothing, and a new approved acceptance criterion, GE-113c-1-vi, specifies the fix: find the package in every layout the build ships, block when it cannot be found, and never be switched off again to let errors through."
description: "Adds KI-CG-20260928-check-agent-registry-never-runs-in-this-repo and approved AC GE-113c-1-vi under GE-113c-1. The hook resolves package_root as <repo root>/leafcutter and returns 0 when that path is missing; here the package sits at the repo root, so every 'Check Agent Registry ... Passed' was empty, while build.py --validate-only still validated the registry. GE-113c-1-vi reuses the shared project-root resolver plus the build manifest's package_root, blocks with its own message when a scoped file is staged and no package is found, keeps parity between the live and packaged copies, and forbids re-disabling the check. An enablement preview found no registry errors. The parent GE-113c-1 gains the test contract the AC schema check requires once it is staged."
commits: []
breaking: false
---

## Entry

The check that is meant to validate the agent registry on every commit has
never run in this repository. It looks for a `leafcutter/` folder that only
some installs have, finds nothing, and reports success. The registry was
still checked by the build, just never at commit time.

This change records the problem as a known issue and adds an approved
criterion for the fix. The check will find the package wherever the build
puts it, refuse the commit when it cannot find it, and stay switched on. A
trial run found no errors in the current registry.
