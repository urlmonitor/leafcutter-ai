---
title: "The presence-only assertion check judges only what a merge itself adds"
date: "2026-10-17"
time: "10:30"
type: manual
components: 
  - commit_guardian
summary: "check-presence-only-assertions no longer refuses a merge of main for presence-only test assertions the merged-in branch already added; it judges the merge's own authored change, like the other merge-aware checks."
description: "The hook read a bare git diff --cached, so in a merge every line main added since the branch point counted as added by the merge (found merging 260 main commits into the BO-4300 epic: two of main's own tests, byte-identical to main, were refused). During a merge, revert or cherry-pick it now takes the diff from the shared _authored_change.get_authored_change() (GE-120e-1); a plain commit is unchanged, and a derivation that cannot be computed reports could-not-check rather than falling back to the unscoped diff. Tests: unit_tests/commit_guardian/test_presence_only_merge_aware.py (real temporary repos: a carried-in assertion passes, an assertion the resolution adds is refused, a plain commit is still refused). TICKET-20261017-PresenceOnlyMergeAware."
commits: []
breaking: false
---

## Entry
