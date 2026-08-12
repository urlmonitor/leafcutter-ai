---
title: "fix(done-proof): exclude fixture paths from proof-of-done AC discovery"
date: "2026-08-12"
time: "14:20"
type: manual
components: 
  - commit_guardian
  - precommit_hooks
summary: "Proof-of-done gate no longer evaluates bundled fixture or demo AC copies, preventing false-positive gate failures on PRs that ship Atlas mock-mode fixture data."
description: "1 commit (2cc9b35). Refactored the duplicated path filter in _get_staged_ac_yaml_paths and _get_changed_ac_yaml_paths into a pure _is_gated_ac_yaml() predicate that excludes any YAML path containing a fixtures segment. Unit-test coverage added in test_done_proof_excludes_fixtures.py (59 lines). Durable fix for the PR #410 workaround that dropped fixture ACs to in_progress."
pr: 412
commits: 
  - 2cc9b35
breaking: false
---

## Entry
