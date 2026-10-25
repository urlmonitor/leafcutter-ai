---
title: "KI-BO-20261023-test-breaker-no-op-alterations — test-breaker can prepare a wrong version that changes text but not behaviour, and the runner cannot tell, so a test that would catch the real wrong version is reported as a blocking survivor"
description: "medium — the wrong-version runner refuses an alteration only when it does not load (did_not_load) or changes no bytes (not_applied). An alteration that changes text the tested path never reads passes both checks, every test passes under it, and each passing test is a blocking survivor. Observed 2026-10-22 on TQ-500g-2-ii: two of test-breaker's replacements (an os.environ.setdefault of a variable nothing reads, and a pop on the copy a computed @property returns) came back as survivors; a manual diagnosis showed the tests were sound and faithful replacements were caught."
type: reference
category: reference
status: active
created: '2026-10-23'
last_updated: '2026-10-23'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-20261023-test-breaker-no-op-alterations — a wrong version that changes no behaviour reads as a weak test

> Filed 2026-10-23. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** medium. The runner fails closed, so nothing wrong is committed. But each false
  survivor halts the drive. The operator then has two bad choices: judge that the test is weak
  and weaken the requirement or the test, or re-prepare blind and hope the next reply is
  faithful. Only a manual trace shows which is true.
- **Status:** open, no AC.
- **Occurrences:** 2 alterations in 1 drive (2026-10-22, TQ-500g-2-ii).
- **First seen:** 2026-10-22 · **Last seen:** 2026-10-22
- **Where** (line numbers at `origin/main` `212a126bf`):
  - `templates/agents/test-breaker.md`:140-171, the `## Replacements` rules. They ask for a
    minimal change that "does what the name says" (:158), that still loads (:163) and that
    differs from `old` (:165-166). Nothing asks the agent to check that the changed value is
    read on the path the name describes.
  - `scripts/build_orchestration/wrong_version_runner.py`:171-186, `_files_for`. The only
    content check is a byte comparison against the file as written; no change gives
    `not_applied` (:186).
  - `scripts/build_orchestration/_wvr_verdict.py`:44-72, `read_one`. A `PASSED` outcome is
    `survived` (:61-62), whatever the alteration did. `did_not_load` covers only a collection
    failure (:58-59) or an import, name or attribute failure (:68-69).

## Symptom

`wrong_version_gate.py finish` stops with `reason: survivor`. The survivor rows read
"passed under '<name>': the test did not notice it", for tests that do test the named
behaviour.

## What happened

On TQ-500g-2-ii, two `must_catch` names were prepared like this:

1. "runner falls back to a default address" became
   `os.environ.setdefault("TEST_DATABASE_URL", ...)`. Nothing on the runner's path reads that
   variable, so the runner's behaviour did not change.
2. "extra named like a must_catch name downgrades it to non-blocking" became
   `test.versions.pop(...)` on a computed `@property`. The property builds a new list on each
   access, so the pop changed a copy that was then thrown away.

Both alterations loaded and both changed bytes, so the runner ran them. Every test passed and
each came back as a blocking survivor. A manual diagnosis (apply the alteration in a scratch
copy, trace the value) showed the alterations were no-ops. Replacements that changed the value
at the decision point were caught by the same tests.

## Mechanism

1. **The preparer is told what to change, not where the change takes effect.** The name is
   prose. The agent picks a line that mentions the right concept. Nothing in its instructions
   asks it to follow the value to the code that decides the outcome.
2. **The runner checks form, not effect.** It proves the alteration loads and changes text.
   It cannot tell a change on a dead path from a change on the live path.
3. **A pass is read as the test's fault.** `read_one` maps every `PASSED` to `survived`. So a
   no-op alteration and a weak test give the same row.

## Detection

A survivor where the replacement's `new` sets a value (environment variable, attribute, list
element) and a grep for that value on the named path finds no reader, or where it changes the
result of a call that is not stored. Confirm by applying the alteration in a scratch copy and
tracing whether the changed value reaches the decision point.

## Workaround

Diagnose each survivor by hand before changing any test: apply it in a scratch copy and trace
the changed value. If it is a no-op, re-prepare with an explicit instruction to change the
value where the decision is made.

## Suggested fix

Directions only; nothing here is applied.

- **Prompt.** Add a rule to `test-breaker.md`'s `## Replacements`: trace that the changed value
  is read on the path the name describes, and prefer changing the decision point itself (the
  condition, the returned value) over a setting or a copy upstream of it. An alteration whose
  effect cannot be traced is `could_not_prepare`.
- **Runner, optional.** Refuse an alteration that changes no line executed by the tests in
  scope, using line coverage of the as-written run. Report it as unfinished with its own word
  (for example `not_executed`), not as a survivor.
  **Partly applied by TQ-500g-1-xiv:** the runner now traces the as-written run and reports a
  test that runs none of a wrong version's changed lines as `not_executed` (unfinished, never a
  survivor), per test. This covers the case where a test never reaches the changed line. It does
  not cover an alteration whose changed line is run but whose effect is dead (the two cases
  above: an unread environment variable, a copy thrown away); those still read as survivors.
  See [Reached or not executed](../../reference/wrong-version-runs.md#reached-or-not-executed).
- **Triage, optional.** Before a survivor stops the gate, ask a separate step whether the
  alteration is behaviourally equivalent to the code as written, and report the answer next
  to the survivor row.

**Pattern:** a check that proves a mutation is well-formed and different, read as proof that it
changes behaviour.
