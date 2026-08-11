---
title: "changelog-presence CI gate"
date: "2026-08-11"
time: "13:00"
type: feature
components: 
  - build_orchestration
summary: "Added a CI gate that blocks a PR when it changes releasable content but adds no changelog entry, so work can no longer reach main without triggering the auto-release."
description: "New scripts/release/check_changelog_presence.py (stdlib-only) plus a changelog-presence job in .github/workflows/ci.yml: on pull_request it fails when the PR diff vs origin/main touches releasable files (anything outside changelogs/, tickets/, docs/acceptance-criteria/) but adds no new changelogs/ entry. Covered by 14 unit tests. Closes the silent-accumulation gap where PRs merged without a changelog never bumped the version (compute_next_version reads changelog entries since the last tag)."
breaking: false
---

## Entry
