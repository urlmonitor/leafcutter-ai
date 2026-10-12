---
title: "KI-TQ-20261006-one-validator-run-reports-as-ten-test-failures — every test in test_uxp_300.py asserts the exit code of the same validate_product_truth.py pass over the real store, so one refusal is reported as nine or ten independent failures"
description: "low — the failure count inflates a single root cause by an order of magnitude and distorts triage: a reviewer reads ten broken behaviours where there is one unrunnable validator. Confirmed by re-run on main 46a6033d (10 failed, all carrying one identical assertion message from one validator invocation). The specific CI cause reported (AssertionError: 1 != 0, nine failures) was NOT reproduced locally — the local run fails with 2 != 0 for a different reason."
type: reference
category: reference
status: active
created: '2026-10-06'
last_updated: '2026-10-06'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/testing-quality/open-high-ki-tq-20261006-corpus-size-assertions-go-red-on-routine-authoring.md
---

# KI-TQ-20261006-one-validator-run-reports-as-ten-test-failures — every test in test_uxp_300.py asserts the exit code of the same validate_product_truth.py pass over the real store, so one refusal is reported as nine or ten independent failures

- **Severity:** low. Nothing is silently wrong and nothing is blocked — the harm is entirely in triage: the failure count is not a count of defects, and a reviewer sizing a red set by its line count mis-sizes this one tenfold.
- **Status:** open. No AC of its own. Noted alongside `KI-TQ-20261006-corpus-size-assertions-go-red-on-routine-authoring`, found in the same CI run.
- **Occurrences:** 1 CI run (9 failures, each `AssertionError: 1 != 0`) + 1 local re-run (10 failures, each `AssertionError: 2 != 0`).
- **First seen:** 2026-10-06 · **Last seen:** 2026-10-06
- **Reported by:** found while investigating an unrelated CI failure set.
- **Where:** `unit_tests/product_truth/test_uxp_300.py` — `TestUxp300BoundedBehavior` (8 tests) and `TestTheStorePassesItsOwnValidator` (2 tests).

## Mechanism

Each test in both classes ends by asserting that a `validate_product_truth.py` run over the **real** `docs/product-truth/` store exited `0`. When that one run refuses for any reason, all ten assertions fail with the identical message, because they are all reading the same number.

## Evidence

Reported CI shape: nine failures, every one `AssertionError: 1 != 0`.

Local re-run on main `46a6033d`:

```text
python -m pytest unit_tests/product_truth/test_uxp_300.py -q --tb=line
10 failed, 5 passed, 12 subtests passed in 38.05s
```

All ten carry the same text, which is the validator's own refusal message, not ten different assertion sites:

```text
AssertionError: 2 != 0 : FAIL: jsonschema is required for product-truth validation
but is not installed. ... Refusing to run — schema validation must not silently no-op.
```

So the fan-out shape — N test failures, one cause, one shared number — is confirmed independently of the CI run's specific cause.

## What could not be confirmed

- **The CI cause.** The reported `1 != 0` was not reproduced; locally the validator returns `2` for a different reason, so the nine CI failures and these ten local failures are the same *shape* with different *causes*.
- **The local cause is itself unexplained** and may be a second defect: `jsonschema` 4.10.3 *is* importable from the same working directory under the same interpreter (`python -c "import jsonschema"` succeeds, Python 3.12.3), yet the validator the test invokes reports it as not installed. That points at the validator's own import path or the environment it is spawned with — not investigated here, and not this entry's subject.

## Detection

A failure block in which every listed test carries a byte-identical assertion message, and the message is the output of a tool rather than a description of the behaviour under test. Count distinct messages, not failing test ids.

## Suggested fix

Run the validator **once** in a class- or module-scoped fixture and assert its exit code in **one** test. The other tests should then assert their own distinct property of that run's output (which rule fired, which artifact was named), so a validator that cannot run produces one failure that says so, and a store that is genuinely wrong produces one failure per wrong thing.

**Pattern:** a shared precondition asserted once per test instead of once per suite. The failure count then measures the number of tests, not the number of problems.
