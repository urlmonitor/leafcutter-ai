---
title: "Salvage the safe, finished work from stalled PR #489 (EPIC-DeploymentCompleteness)"
date: "2026-08-24"
time: "09:01"
type: manual
components: 
  - template_compiler
  - testing_quality
summary: "Recovered the safe, already-tested portion of a stalled internal build-tooling branch onto main; this is internal tooling and documentation hardening with no new capability for adopters."
description: "Cherry-picks the safe subset of the unmerged EPIC-DeploymentCompleteness branch (PR #489) onto current main, covering ACs BP-900b-1, BP-900a-3, BP-900c-1 plus BP-900b-1-1 test coverage (10 files, 1729 insertions). BP-900b-1 adds extract_compiled_script_path_refs() to scripts/build_referential_integrity.py, scanning a COMPILED output tree (.claude/agents/, .claude/skills/) for script references as the post-compile counterpart to the existing pre-build extractors -- not yet wired into a build.py phase, a known follow-up. BP-900a-3 and BP-900c-1 are documentation closures plus previously-missing tests for behaviour that already existed on main. 4 new test files add 16 tests, green under AC_ENFORCE_STRICT=1. Deliberately excludes the sibling AC BP-900a-2, which was destructive in the self-hosted layout (its deploy shims replaced the tracked scripts/goal_to_epic.py with a self-importing delegator, causing a circular ImportError) -- filed separately as a known issue; the epic is not complete."
commits: 
  - 112b7cba
breaking: false
---

## Entry
