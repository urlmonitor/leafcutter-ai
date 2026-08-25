---
title: "Aiming the fast lane at one criterion now builds that criterion, not its parent's siblings"
date: "2026-08-19"
time: "14:05"
type: manual
components: 
  - build_orchestration
summary: "The lane now resolves its build set with structural-parent prerequisites excluded, so pointing it at a leaf no longer drags in unrelated work that merely shares a parent."
description: "templates/workflows-js/fast-lane-ship.js now passes --exclude-structural-parent when it composes its select_connected command. Before this, aiming the lane at a leaf walked that leaf's depends_on up to its structural parent, then that parent's parent, and expanded every not-done leaf underneath — so BO-2400c-1-i resolved to five criteria including two the operator had not asked for and one deliberately parked. With the flag it resolves to exactly BO-2400c-1-i. No new capability was needed: resolve_connected_build_set already accepted exclude_structural_parent, the CLI flag already existed, and templates/agents/build-ac.md already passed it; only the fast lane did not, so the two entry points disagreed about what a build set is. The exclusion is unconditional and there is deliberately no per-run switch. It suppresses only the depends_on walk and never the subtree gathered beneath the aimed-at criterion, so an operator who wants a whole branch aims at the branch — no scope is unreachable. A per-run option would have had to pick a default, and both are worse: default-include leaves the broken scope as what you get by default, and default-exclude ships a documented way to opt back into the explosion. The nothing-to-build payload also now states that structural-parent prerequisites were excluded, and carries an explicit structural_parent_excluded field, so an operator can tell a genuinely empty set apart from one the exclusion emptied — a bare nothing to build cannot distinguish those. Covered by nine tests that execute the lane under the workflow-engine harness, extract the resolver command the lane actually composed, and re-run it as a real subprocess against fixture stores, asserting on the returned id list. None of them greps the workflow source, because a presence-grep passes on a commented-out flag, a flag on the wrong subcommand, and dead code. One is a seam test that stays green throughout and exists to catch the fix being made in the wrong place — changing the library default, which BO-2600a-1 fixed at False as a backward-compat invariant, or editing build-ac.md."
commits: []
breaking: false
---

## Entry
