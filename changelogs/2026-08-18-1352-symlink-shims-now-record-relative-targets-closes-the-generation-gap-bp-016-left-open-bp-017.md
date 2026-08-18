---
title: "Symlink shims now record relative targets — closes the generation gap BP-016 left open (BP-017)"
date: "2026-08-18"
time: "13:52"
type: manual
components: 
  - build_pipeline
summary: "Fixed the build so the shortcut files it creates no longer bake in one developer's own computer path, closing the actual hazard that BP-016's changelog entry title was mistakenly read as having already handled."
description: "BP-016 (2026-08-14) fixed only the tracking half of this hazard: it stopped the five absolute-path shims from being committed into git, which fully resolves the problem for this repo because build output here is untracked by design. It left the generation step itself untouched — install_shims() still built canonical_path and source_path as absolute paths and passed the absolute source straight into Path.symlink_to() for every shim, in both _create_shim (directory shims) and _create_file_shim (file shims). Anyone who vendors or copies this repo's build output into a consumer project inherited that absolute, machine-specific target regardless of the git-tracking fix, and the resulting links go dangling the moment the tree is copied, rsynced, or bind-mounted elsewhere — which is what made BP-016's original damage possible in the first place. BP-017 fixes generation: a new _relative_symlink_target() helper computes the recorded target with os.path.relpath(source, canonical.parent) — relative to the link's OWN parent directory, not the process's invocation cwd, which matters because a naive relpath-from-cwd form breaks (e.g. a bare '.leafcutter/agents' recorded at '.claude/agents' resolves to the wrong location, '.claude/.leafcutter/agents'). Both shim depths are covered: nested shims one level down (.claude/agents, scripts/commit_guardian) now read back with one leading '../' step, and root-level shims (.gemini, .pre-commit-config.yaml) read back with zero. When canonical and source share no common ancestor (different drives/mounts), os.path.relpath raises ValueError and the helper falls back to an absolute target so the build still completes rather than raising. Verified behaviorally: a real build into a foreign consumer directory, then physically relocated to a different absolute path, leaves zero dangling links. Covered by 10 new tests in unit_tests/build_guards/test_bp017_shim_relative_targets.py (all green), which exercise the real install_shims() against real temporary directories and read links back with os.readlink()/Path.resolve() rather than mocking the symlink call."
pr: 477
adrs: 
  - ADR-004
  - ADR-016
tickets: 
  - BP-017
commits: 
  - 1d10b6b96
breaking: false
---

## Entry
