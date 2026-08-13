---
title: "Changelog PR #422 — fast-lane lifecycle CLI wiring (BO-2400f phantom-done fix) — 2026-08-13"
date: "2026-08-13"
time: "12:00"
type: manual
components: 
  - build_orchestration
summary: "Fixed the fast lane so it actually claims, releases, and marks-done an AC's work status during a real build run, instead of that logic sitting unused in code that only unit tests were calling."
description: "1 commit (b34ed1c0a), PR #422 — fix(fast-lane): wire AC work_status lifecycle into the fast-lane run path. PR #411's five lifecycle functions (claim_build_set, release_claim, filter_already_claimed, mark_done_built_acs, check_no_stale_todo) shipped with a 1402-line unit test but no CLI subcommand and no caller in fast-lane-ship.js — an audit found zero production callers, so the start-side claim/skip/release half of BO-2400f was dead code that still passed every gate because the pipeline's done-proof only checks that a `# covers:` unit test imports and exercises the function directly. This adds `claim`, `release`, and `mark_done` CLI subcommands to fast_lane.py (JSON to stdout even on refusal/stale paths, coverage-gated mark_done plus the stale-todo guard, idempotent release), and wires fast-lane-ship.js to claim the connected set after Resolve (halting if a concurrent run already owns it), release this run's claims on all five post-claim failure branches (test-writer, red-baseline, coder, coverage, commit), and replace the per-id mark_ac_done.py loop with a single coverage-gated mark_done at Commit. Adds unit_tests/build_orchestration/test_fastlane_lifecycle_cli.py (703 lines, drives the CLI entry point and asserts real on-disk YAML transitions rather than importing the functions directly) and extends unit_tests/workflows/test_fast_lane_ship_structure.py to assert the claim/release/mark_done wiring. pr-reviewer caught two HIGH defects fixed before merge: the commit-phase failure path previously returned without releasing (leaking claims permanently stuck in_progress), and releaseInvocation was originally built from the full resolved set before the claim response was known (could reset a concurrent run's claims) — now scoped to claimResult.claimed. 4 files changed, 1115 insertions(+), 16 deletions(-). 21 new/extended tests green, 501 tests green across unit_tests/build_orchestration/ + unit_tests/workflows/, ruff clean, node --check passes, and behaviorally verified against the real AC store (BO-2400e-2 flipped todo->in_progress via the CLI and back)."
pr: 422
commits: 
  - b34ed1c0a
breaking: false
---

## Entry
