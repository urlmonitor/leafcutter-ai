---
title: "Test coverage for the skill-reference guard"
date: "2026-08-19"
time: "17:47"
type: manual
components: 
  - build_pipeline
summary: "Covers scripts/check_skill_refs.py with eight tests, so the guard against dangling skill references is itself verified."
description: "Adds unit_tests/test_check_skill_refs.py, covering scripts/check_skill_refs.py, which shipped in #497 without tests. A guard with no tests is the failure mode this package exists to prevent, one layer up: nothing distinguished a working checker from one that always exits 0. The suite asserts both directions -- a resolvable Load instruction passes, a dangling one fails, and a dangling `python .../emit_event.py` invocation fails -- so a no-op checker breaks the suite rather than passing it. Verified by mutation: forcing the pass branch unconditionally turns two tests red, confirming they genuinely constrain the implementation rather than asserting on dead code. The two discriminators that keep the guard off accurate history each get a test: an HTML DECISION HISTORY comment naming the correctly-retired create-ac skill must not fail, and a descriptive prose mention must not fail. Also covers the dedupe of the two path forms written on one line (the `.claude/skills/x` (or `templates/skills/x`) pair that PO/BA/IT-PO v3 all use), which would otherwise double every count in the report, and the missing-templates/skills hard error returning 2 rather than a misleading 0. Corrects one factual error in the checker's module docstring: it described nine emit_event.py invocations in the building-epics runbook where there are eight, the number the KI-BP-007 entry already carried."
breaking: false
---

## Entry
