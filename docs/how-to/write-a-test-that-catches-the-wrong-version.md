---
title: "How to write a test that catches the plausible wrong version"
description: "Guard a bug fix or a gate change with a test that goes red under named wrong versions of the code, not only when the code is missing. Worked through on the refresh-gate retry storm."
type: how-to
status: active
created: 2026-10-07
last_updated: 2026-10-07
components:
  - testing_quality
  - ac_store
related_docs:
  - docs/testing/test-angles.md
  - docs/analysis/2026-09-25-test-writers-prove-failure-not-discrimination.md
  - docs/reference/ac-schema.md
  - docs/how-to/prove-ac-done.md
related_code:
  - scripts/build_orchestration/_fl_red_baseline_support.py
---

# How to write a test that catches the plausible wrong version

You are guarding a bug fix or a change to a gate, and you want a test that goes red under the wrong versions of the code someone could plausibly write, so that a green suite means the fix is still there.

## Prerequisites

- A bug fix or gate change to guard, and the production code's current (fixed) form.
- A requirement (AC) whose `test_spec` entry you can edit, or a test requirements entry you are about to write. See [`docs/reference/ac-schema.md`](../reference/ac-schema.md) for the `must_catch` field.
- Read [`docs/testing/test-angles.md`](../testing/test-angles.md) once. It holds the failure catalogue; this guide does not repeat it.
- Optional background: [the analysis behind this guide](../analysis/2026-09-25-test-writers-prove-failure-not-discrimination.md). Incident 1 there is the worked example below.

The worked example: a cache refresh gate went from `if refresh_due:` to `if refresh_due and retry_due:`, so that a database outage no longer causes a retry storm. Two of three tests were updated to satisfy both conditions. The third reset only `refresh_due`. The branch under test ran 0 times, and the suite stayed green.

## Steps

### Step 1 - Name the wrong versions first

Before writing any test code, list the versions of the code that would bring the bug back. Write at least:

- **Revert the fix.** The gate is `if refresh_due:` again.
- **One "drop condition X" per condition of the gate.** The gate has two conditions, so there are two: drop `retry_due` (the gate is `if refresh_due:`, which equals the revert here) and drop `refresh_due` (the gate is `if retry_due:`, which refreshes when nothing is due).

For the refresh gate the list is:

1. `revert the fix`
2. `drop the retry_due condition`
3. `drop the refresh_due condition`

Keep each name short and concrete enough that someone could apply it to the file by hand.

### Step 2 - Record them as `must_catch` on the test entry

Put the names on the requirement's `test_spec` entry for this test. When present, `must_catch` must be a non-empty list and every item must contain at least one non-whitespace character. The `check-ac-schema` validator refuses an empty list, a blank item, and a bare string, and its error names the entry, the field and the rule that failed. Declaring `must_catch` also makes the red-baseline reader refuse an absence-only red for this entry (see Step 8).

```yaml
test_spec:
  - name: test_refresh_is_skipped_while_retry_not_due
    target_dir: unit_tests/config_cache/
    framework: pytest
    type: integration
    angle: discrimination
    description: Refresh does not run while the retry window is closed, and does run once it opens.
    must_catch:
      - revert the fix
      - drop the retry_due condition
      - drop the refresh_due condition
```

Ticket generation copies the list verbatim onto the `## Test Requirements` entry. Do not infer `must_catch` from the criteria text: the criteria-derived fallback never adds it, so you name the wrong versions yourself.

### Step 3 - Answer the three questions for the test

Answer all three for each test that guards the change, in the test's report:

| Question | Answer for the refresh gate |
|---|---|
| Q1: What is the smallest change to the production code that keeps this test green but brings the bug back? | Dropping `retry_due`. The third test set `refresh_due` and never `retry_due`, so it ran the same under `if refresh_due:` and under the new gate. The branch ran 0 times. |
| Q2: What result would show this assertion can fail, and does the fixture produce that result? | A refresh call count of 1 where 0 is expected (retry window closed), or 0 where 1 is expected (both open). The old fixture produced neither: it never reached the branch. |
| Q3: Does the control row pass for a different reason than the negative row fails? | The control (both conditions true) must pass because both hold. The negative (`retry_due` false) must fail only because `retry_due` is false. In the old fixture neither row set `retry_due`, so both were excluded by the same missing input. |

Label each answer `observed` only when it cites output from a run you performed in this phase (for example a run under one of the named wrong versions); otherwise label it `reasoned`.

When the entry carries `must_catch` (or `angle: discrimination`), each listed wrong version is a Q1 answer you must defeat first: every one must be a version the test would catch. When Q1 names a change that would keep the test green, strengthen the test until that change would turn it red, then list the named change in your report as a wrong version the test now catches.

### Step 4 - Go through the vacuity checklist, item by item

Go through all four items for each test. An item that does not apply is marked `not applicable: <one-line reason>`; never leave it out. For each item, the weak version and the strengthened version follow.

**Item 1: the assertion states an exact count, not a one-sided bound (`== 3`, not `>= 1` or `>= 0`).**

Weak:

```python
def test_refresh_runs(cache, db):
    cache.tick()
    assert db.load.call_count >= 0
```

Strengthened:

```python
def test_refresh_runs_once(cache, db):
    cache.tick()
    assert db.load.call_count == 1
```

**Item 2: a control row that must pass is present alongside the negative row.**

Weak (only the negative case, so a gate that never opens also passes):

```python
def test_no_refresh_while_retry_closed(cache, db):
    cache.refresh_due = True
    cache.retry_due = False
    cache.tick()
    assert db.load.call_count == 0
```

Strengthened (add the control, where both conditions hold):

```python
def test_refresh_follows_retry_window(cache, db):
    cache.refresh_due = True
    cache.retry_due = False
    cache.tick()
    assert db.load.call_count == 0

    cache.retry_due = True
    cache.tick()
    assert db.load.call_count == 1
```

**Item 3: every new input the change reads is seeded with values distinct from the old inputs, so the old input cannot satisfy the new branch.**

Weak (the new input keeps its default, so it matches whatever the old fixture implied):

```python
cache = make_cache(refresh_due=True)  # retry_due left at its default
```

Strengthened (set the new input explicitly, once true and once false):

```python
cache = make_cache(refresh_due=True, retry_due=False)
```

**Item 4: the test counts calls on the collaborator the new branch must reach.**

Weak (checks a side effect any path could produce):

```python
cache.tick()
assert cache.last_error is None
```

Strengthened (counts the call the branch exists to make):

```python
cache.tick()
assert db.load.call_count == 1
```

### Step 5 - Write a fixture that satisfies every condition of the compound gate

The failing fixture satisfied one condition. For a compound gate, set every input the gate reads, on purpose, in every test that is meant to reach the branch. In the refresh example, the reaching fixture is:

```python
cache = make_cache(refresh_due=True, retry_due=True)
cache.tick()
assert db.load.call_count == 1
```

Then sweep: list every other test that exercises this gate or its helper. Update each one, or state in the report why it is unaffected. One test that resets only the old variable is how the 0-call branch got through.

### Step 6 - Assert the call count

Assert the number of calls to the collaborator the branch reaches, using the exact count from Step 4 item 4. A pass that does not touch the branch proves nothing. A count of 1 where the branch runs, and 0 where it must not, is the measurable evidence that the fixture reached the code.

### Step 7 - Check the test goes red under each wrong version

Apply each named wrong version to the production file by hand, run the test, then restore the file.

```bash
python -m pytest unit_tests/config_cache/test_refresh_gate.py -q
```

Record the result for each:

| Wrong version | Expected |
|---|---|
| revert the fix | red: `assert 1 == 0` on the closed-window call count |
| drop the retry_due condition | red: same assertion |
| drop the refresh_due condition | red: the control step finds 1 call where nothing is due, or the first call count is wrong |
| (none applied, fixed code) | green |

Revert each alteration and re-run to confirm the test returns to green before you continue.

If any wrong version leaves the test green, the test is weak: go back to Step 4 and strengthen it.

### Step 8 - Check that the red is an assertion, not an absence

A red caused only by a missing import or name proves the code is absent. It does not prove the test guards code that already exists.

Absence-shaped red:

```text
ImportError: cannot import name 'retry_due' from 'config_cache'
```

Assertion-shaped red:

```text
AssertionError: assert 1 == 0
 +  where 1 = <Mock name='load' id='...'>.call_count
```

Only the second shows the test reached the code and the code behaved differently from the one the test expects. The red-baseline reader treats the two differently for declared entries: when a newly added test's `test_spec` entry carries `must_catch` (non-empty) or `angle: discrimination`, and its only red is an absence red, the reader refuses it as red evidence: the test moves to the result's `refused` list and the gate fails closed with reason `declared_test_refused_absence_only_red`. It reads this from the entry itself and never from the criteria prose. Pass `--ac-root` to opt in:

```bash
python scripts/build_orchestration/fast_lane.py verify_red_baseline --ac-ids TQ-500f-6 --test-root unit_tests --ac-root <ac_store_root>
```

Omit `--ac-root` and the reader behaves as it did before this rule.

## Verification

Run the guarding test on the fixed code:

```bash
python -m pytest unit_tests/config_cache/test_refresh_gate.py -q
```

Expected: all tests in the file pass. Then confirm Step 7's table holds: each named wrong version, applied by hand, makes at least one test fail with an assertion error, and removing it brings the suite back to green. If a wrong version stays green, see Troubleshooting.

## Troubleshooting

1. **A wrong version leaves the test green.** The fixture does not reach the branch, or the assertion is one-sided. Set every condition of the gate in the fixture, and replace any `>=` or truthiness check with an exact call count.
2. **The red-baseline reader refuses your test.** The only red was an import or name error. Run the test against the existing code so it fails on an assertion, or write the stub so the symbol exists and the assertion fails.
3. **The validator rejects `must_catch`.** The list is empty, an entry is blank or whitespace-only, or the value is a single string. Give it a non-empty list of non-blank strings.
4. **You cannot name a wrong version.** Say so in the report and give what you tried. Do not invent a name to fill the field.

## Related work not yet built

Phase B of the plan (`TQ-500g`) is planned to run the named wrong versions automatically and block sign-off if any survives. It is not built yet. Until it lands, Step 7 is something you do by hand, and the `must_catch` list is what that automation will read.

## See Also

- [Test angles taxonomy](../testing/test-angles.md) - the full failure catalogue and the angle definitions.
- [Analysis: test writers prove failure, not discrimination](../analysis/2026-09-25-test-writers-prove-failure-not-discrimination.md) - incident 1 and the three questions in full.
- [AC schema reference](../reference/ac-schema.md) - `test_spec` and `must_catch` fields.
- TQ-500d-2 - the sibling how-to for work whose tests pass on arrival and need substitute evidence. It covers a different case; this guide does not.
- [How to prove an AC is done](prove-ac-done.md)
- [Documentation Index](../INDEX.md)
