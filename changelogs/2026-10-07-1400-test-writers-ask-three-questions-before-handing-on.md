---
title: "Test writers ask three questions before handing on, and say which red they saw"
date: "2026-10-07"
time: "14:00"
type: manual
components:
  - testing_quality
summary: "Both test-writing agents now check each guarding test against three questions and a four-item vacuity checklist before handing on. The ordinary test writer labels each red as absence or assertion. A new how-to and the test-angle reference cover the discrimination angle and must_catch."
description: "TQ-500f-3 prompt part, TQ-500f-4, TQ-500f-4-i, TQ-500f-4-ii, TQ-500f-5, TQ-500f-6 (prompt and docs ACs, test_required: false, orchestrated manually). test-writer.md: an ImportError/AttributeError red is evidence of absence only; the Step 4 table splits assertion red from absence red; a zero-exit run is fixed with a stronger assertion, never a comment; red_baseline entries carry kind. New Step 4b in test-writer.md and sql-test-writer.md: Q1-Q3, the vacuity checklist (exact count, control row, distinct new inputs, collaborator call count; not applicable needs a reason), the NULL-skipping and presence-not-correctness patterns, and the refresh_due/retry_due worked case. sql-test-writer labels every answer reasoned and lists Q1 wrong versions under To run later. docs/testing/test-angles.md has eight angles with discrimination as a conditional one; docs/testing/test-angles-failure-catalogue.md gains a discrimination-shaped failure family (incidents 1, 2, 3, 4, 8) beside the wiring-shaped one. Both ac-schema.md copies document angle: discrimination and must_catch. New how-to: docs/how-to/write-a-test-that-catches-the-wrong-version.md. TQ-500f-3 stays in progress until TQ-500f-3-iii and -3-iv are built; TQ-500f-4 stays in progress until the composite done-proof can prove prompt-only children (KI-CG-20260914)."
commits:
breaking: false
---

## Entry

A failing test used to count as proof that it guards the code, even when it failed only
because the code was missing. The test-writing agents now treat that kind of red as proof
of absence and nothing more. Before handing a test on, they ask what wrong version would
still pass it, whether its assertion can fail at all, and whether its control row proves
anything, and they fix the test until it holds up. The database test writer does not run
its tests, so it marks its answers as reasoning and lists the wrong versions for a later run.
A new how-to walks requirement authors through naming those wrong versions as must_catch.
