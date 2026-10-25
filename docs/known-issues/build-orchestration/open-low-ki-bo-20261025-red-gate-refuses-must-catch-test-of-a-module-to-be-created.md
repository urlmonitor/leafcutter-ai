---
title: "KI-BO-20261025-red-gate-refuses-must-catch-test-of-a-module-to-be-created — an AC that declares a new module and names a wrong version for a unit test of it cannot pass the red-baseline gate without a skeleton module"
description: "medium — the red-baseline reader refuses an absence-only red (import error) for any test whose test_spec entry names must_catch. When the AC's declared_files marks the module to_be_created and a must_catch test imports a function from it, the only red the test-writer can produce is an import error, so the drive halts before the coder. Seen on TQ-500g-1-xiv (2026-10-25), cleared by a skeleton module raising NotImplementedError."
type: reference
category: reference
status: active
created: '2026-10-25'
last_updated: '2026-10-25'
components:
  - build_orchestration
  - testing_quality
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500g-1-xiv.yaml
---

# KI-BO-20261025-red-gate-refuses-must-catch-test-of-a-module-to-be-created

> Filed 2026-10-25. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** medium. The gate fails closed, so nothing is wrongly built, but the ticket halts
  before its coder runs and a person has to decide how to unblock it.
- **Status:** open, no AC.
- **Occurrences:** 1, run `wf_c4f8ba47-9c0`, ticket 04 (TQ-500g-1-xiv).
- **First seen:** 2026-10-25 · **Last seen:** 2026-10-25

## Symptom

`verify_red_baseline gate failed ... Reason: declared_test_refused_absence_only_red`, refusing
`test_changed_lines_of_replace_delete_and_insert` with "A test naming wrong versions to catch
must fail by reaching the code, not by failing to import or find the thing it names." The other
seven tests of the ticket were red by assertion.

## Mechanism

TQ-500g-1-xiv's `declared_files` lists `scripts/build_orchestration/_wvr_effect.py` with
`state: to_be_created`, and its test_spec gives the pure-function test
`must_catch: ["changed lines taken from the altered side's numbering"]`. The test-writer's own
template (`templates/agents/test-writer.md`, the red-kind table) says an absence red is correct
only for code that does not exist yet, and also that a test declaring `must_catch` must be
rewritten to reach the code. For a function in a module that does not exist yet, those two rules
contradict each other: there is no code to reach.

## Workaround used

A skeleton `_wvr_effect.py` with the agreed signature whose body raises `NotImplementedError`.
The reader classifies every exception other than an import, name or attribute lookup error as
an assertion red, so the gate passes and the python-coder phase writes the body. This is honest
about what is missing, but it relies on the classifier treating `NotImplementedError` as
"reached the code".

## Fix direction (not decided)

Either the reader accepts an absence red when the missing module is one the AC declares
`to_be_created`, or the test-writer is told to write the skeleton itself in that case.
