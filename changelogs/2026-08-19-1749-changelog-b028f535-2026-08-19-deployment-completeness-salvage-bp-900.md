---
title: "Changelog b028f535 — 2026-08-19 — Deployment-completeness salvage (BP-900)"
date: "2026-08-19"
time: "17:49"
type: manual
components: 
  - build_pipeline
  - template_compiler
  - testing_quality
summary: "Consumers installing this package into their own project now correctly receive two previously-missing helper scripts (goal_to_epic and build_ac_mode_detection), alongside documentation and test-coverage closures for already-shipped behavior."
description: "1 commit (b028f535), a rebased salvage of the finished/tested portion of the unmerged EPIC-DeploymentCompleteness branch (PR #489, cherry-picking 0982ca61/8f46a08f/04436149/ebdbde71/1d4125d9/19a4399c), covering ACs BP-900a-2, BP-900a-3, BP-900b-1 (plus BP-900b-1-1 test coverage), and BP-900c-1. BP-900a-2: templates/scripts/goal_to_epic.py and templates/scripts/build_ac_mode_detection.py are now tracked template sources with matching install_shims file_shims entries, so a consumer build deploys both scripts as relative symlinks into <target>/scripts/ (verified via a real build.py --target-dir run into /tmp). BP-900b-1 adds extract_compiled_script_path_refs() to scripts/build_referential_integrity.py, the post-compile counterpart to the existing pre-build extractors, scanning a compiled output tree for script references — not yet wired into a build.py phase, a documented follow-up. BP-900a-3 and BP-900c-1 close documentation and missing-test gaps for already-existing production behavior. 5 new test files / 19 real-artifact behavioral tests pass under AC_ENFORCE_STRICT=1; full suite 3742 passed, 0 failed."
commits: 
  - b028f535
breaking: false
---

## Entry
