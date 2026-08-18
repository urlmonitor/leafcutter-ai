---
title: "fix: coder dispatch guard accepts test-writer evidence (BO-2000e-2)"
date: "2026-08-17"
time: "19:40"
type: manual
components: 
  - build_orchestration
summary: "The BO-2000e-2 pre-coder gate read a pre-drive snapshot and blocked python-coder even after test-writer had written a verified-red suite, making every AC-generated ticket unbuildable. The gate now accepts in-drive and prior-drive test evidence."
description: "BO-2000e-2 always specified two conditions — Test Requirements absent AND no test-writer red-baseline — but the implementation only ever checked the first. hasTestRequirements was computed once from the planner's pre-drive snapshot and re-read as a frozen constant inside the phase loop, so evidence produced by test-writer (priority 5, always before any coder at 6+) was invisible to it. Because no surface has emitted a ## Test Requirements section since v2.0.0, every ticket from the canonical /plan-feature -> /build-ac path hit this and halted at its first coder phase; observed live when EPIC-DeploymentCompleteness halted at batch 1 with test-writer already signed off on 3 verified-red tests. The guard now has three satisfaction routes: a populated ## Test Requirements section (unchanged), a non-empty tests_written list returned by test-writer in the same drive, or existing_test_files from a prior drive verified to still be on disk (required for resume — a signed_off test-writer leaves the needed set and can never re-supply in-drive evidence). Fail-closed is preserved: empty tests_written, an omitted field, no test-writer scheduled, and named-but-missing files all still block. Applied identically to both twins, build-feature.js and build-ticket.js. Adds a node harness that loads and executes the real workflow script against stubbed globals and records which phase agents were actually dispatched — the pre-existing AC-3 tests grep the source and pass on both the broken and fixed code."
---

## Entry

The pre-coder gate (`BO-2000e-2`) refused to dispatch `python-coder` whenever a
ticket lacked a `## Test Requirements` section — including when `test-writer`
had already run in that same drive, derived tests from the ticket's `source_ac`
via its AC-derivation fallback, written them, and verified them red.

Root cause: `hasTestRequirements` was a `const` captured from the planner's
snapshot taken *before any phase ran*; the in-loop guard re-read that frozen
value. Since `test-writer` is priority 5 and every coder is 6+, the guard was
always asserting a fact that was already stale.

Blast radius was the whole mainline: `generate_ticket_from_ac.py` emits no
`## Test Requirements` block, so every ticket from the documented
`/plan-feature` → `/build-ac` path was unbuildable.

The guard now opens on any of three evidence routes and stays closed when none
produce evidence. New behavioral tests execute the workflow rather than
grepping it, and were verified non-vacuous against the pre-fix code.

Filed retroactively as `BO-2000e-2-i` (in-drive evidence), `BO-2000e-2-ii`
(resume), and `BO-2000e-2-iii` (fail-closed cases).
