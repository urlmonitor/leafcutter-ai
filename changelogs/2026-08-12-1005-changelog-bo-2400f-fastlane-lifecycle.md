---
title: "Changelog BO-2400f — AC work_status lifecycle baked into the fast lane — 2026-08-12"
date: "2026-08-12"
time: "10:05"
type: manual
components:
  - build_orchestration
summary: "The fast lane now manages an AC's work_status across its whole lifecycle (todo -> in_progress -> done), claiming the resolved set on mainline before building, skipping already-claimed ACs, marking built ACs done coverage-gated, and releasing the claim on failure so work is never left stale or stuck."
description: "1 commit (b98f1bd94), PR #411 — built end-to-end by /fast-lane-build BO-2400f (the fast lane building its own enhancement). Implements BO-2400f-7/-7-i/-7-ii (at build start, claim the resolved set by flipping todo->in_progress on mainline via a merged status-only change first; halt if the claim cannot be recorded; readiness-agnostic), BO-2400f-8/-8-i (the connected-set resolver treats an already-in_progress AC as claimed and skips or refuses rather than rebuilding; a partial-overlap set builds only the todo members; an empty result is a clean no-op), BO-2400f-9/-9-i (at finish, coverage-gated mark-done flips every built AC to done and a passing run that leaves any built AC un-flipped is reported as an error — the stale-todo guard), and BO-2400f-10 (on failure or abort, release the claim in_progress->todo so no AC is left permanently stuck). scripts/build_orchestration/fast_lane.py (+397); unit_tests/build_orchestration/test_bo2400f_lifecycle.py (1402 lines) covers all 8 ACs; the fast lane's verify_green_and_coverage gate and the done-proof pre-commit hook both passed. 10 files changed, 1797 insertions."
pr: 411
commits:
  - b98f1bd94
breaking: false
---

## Entry

Point `/fast-lane-build` at an AC and its work_status now tells the truth at every
stage. The connected build set is claimed (`todo -> in_progress`) on mainline via a
merged status-only change before any test or code work begins, so a concurrent
fast-lane or heavy-lane run excludes the in-flight ACs; an AC already `in_progress`
is treated as claimed and skipped or refused rather than rebuilt; every built AC is
flipped to `done` through the coverage gate at finish (a passing run that leaves one
un-flipped is an error); and on any failure or abort the claim is released back to
`todo` so work is never stranded.
