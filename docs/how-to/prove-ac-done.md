---
title: "How to prove an AC is done with a passing covers-linked test"
description: "Tag a test with # covers:<AC-ID>, understand how the done-proof gate classifies each outcome, and confirm the mechanical gate—not human judgment—is the arbiter of done."
type: how-to
category: how-to
status: active
created: 2026-07-21
last_updated: 2026-07-21
components:
  - build_orchestration
  - testing_quality
related_docs:
  - docs/how-to/done-proof-enforcement.md
  - docs/how-to/fast-lane-build.md
  - docs/architecture/diagrams/c3-done-proof-evaluation-sequence.md
  - docs/architecture/components/build-orchestration.md
---

# How to prove an AC is done with a passing covers-linked test

An acceptance criterion is provably done when at least one test tagged with
`# covers:<AC-ID>` exists in the test tree **and** every such test produces a
`PASSED` outcome in the current pytest run. The mechanical gate — not a
human reviewer — is the sole arbiter of this verdict. This guide covers four
tasks:

1. [Adding a covers tag to a test function](#1-adding-a-covers-tag)
2. [Understanding what the done-proof gate checks](#2-what-the-gate-checks)
3. [Edge cases: how missing, failing, xfail, and skipped tests are treated](#3-edge-cases)
4. [How dangling covers tags are flagged](#4-dangling-tags)

**Design reference:**

- [Done-proof gate enforcement](done-proof-enforcement.md) — the pre-commit hook
  and CI job that run the gate mechanically on every commit and every PR.

---

## 1. Adding a covers tag

Every test function that proves an AC must carry a `# covers: <AC-ID>` comment.
The rule is simple: the tag must be **the first line of the function body**,
immediately after the `def` line and before any other code or docstring.

```python
def test_scanner_rejects_unknown_component():
    # covers: BO-2400a-1
    result = scan(component="not-a-real-component")
    assert result.status == "error"
```

### Placement rules

**The tag must appear inside a test function.** The scanner (`done_proof.py`)
tracks the most-recently-seen `def test_*` definition as the enclosing scope for
any tag on subsequent lines. A tag that appears before the first `def test_`
line in the file — at module level or in a helper function — is silently skipped
and will never link to the queried AC.

**One tag per AC, immediately after the `def` line.** If a single test proves
multiple ACs, add one `# covers:` line per AC, each on its own consecutive line:

```python
def test_full_pipeline_end_to_end():
    # covers: FIN-100a-1
    # covers: FIN-100a-2
    result = run_full_pipeline(fixture="e2e_fixture.yaml")
    assert result.status == "ok"
```

**Tag format.** The tag must appear exactly as `# covers: <ID>` — `#` then a
space, then `covers:` then a space, then the AC id with no trailing whitespace
and no additional text on the same line. The scanner regex is
`#\s*covers:\s*(\S+)`, which accepts any amount of horizontal whitespace around
the colon, so both `# covers:BO-2400a-1` and `# covers: BO-2400a-1` are matched,
but the canonical form with a single space after the colon is preferred.

**Where to put the test file.** Place the test file anywhere under the project's
`test_root` directory (typically `unit_tests/` for this repo). The gate scans
recursively for `*.py` files, so subdirectory organization is up to you.

---

## 2. What the gate checks

The gate is implemented in `scripts/ac_store/done_proof.py` and exposed through
the function `verify_done_eligible(ac_id, *, ac_root, test_root)`. It is invoked
automatically by the pre-commit hook and the CI job on every relevant commit —
you do not run it by hand to declare an AC done.

The gate executes these steps in order:

1. **Scan the test tree.** It reads every `*.py` file under `test_root`
   recursively and collects all `# covers:` tags, associating each with its
   enclosing `def test_*` function.

2. **Collect linked tests.** For the queried `ac_id`, it finds every tag whose
   id matches — these are the "linked tests."

3. **Guard: no linked test.** If no linked test is found, the verdict is
   immediately `eligible: False` with `reason: "no linked test found for <ac_id>"`.
   The rest of the pipeline is skipped.

4. **Run pytest.** It runs `python -m pytest -v --tb=no --no-header` on the
   files that contain linked tests (60-second timeout). The `-v` flag is
   required — exit code alone cannot distinguish `XFAIL` from `PASSED`.

5. **Classify outcomes.** For every linked test, it locates the pytest nodeid
   in the output and reads the outcome string. Only `PASSED` counts as passing.
   `FAILED`, `XFAIL`, `XPASS`, `SKIPPED`, and `ERROR` all count as non-passing
   (the gate is fail-closed).

6. **Return the verdict.** If every linked test passed: `eligible: True`, empty
   reason, and the list of passing nodeids. If any linked test is non-passing:
   `eligible: False` with the failing nodeid named in the reason.

The verdict dict also always carries a `dangling_tags` list (see
[Section 4](#4-dangling-tags)).

---

## 3. Edge cases

### Missing test (no `# covers:<id>` tag for the AC)

**Verdict:** `eligible: False`, `reason: "no linked test found for <ac_id>"`.

The gate treats the absence of any linked test as a hard failure. "I wrote it
and believe it works" is not acceptable evidence — a passing test tagged to the
AC is the minimum bar.

### Failing test (pytest reports `FAILED`)

**Verdict:** `eligible: False`, reason names the failing nodeid.

A test that you tagged with `# covers:<id>` but that currently fails counts
as explicit evidence that the AC is NOT done. Fix the implementation (or the
test, if the test is wrong) before the gate will pass.

### XFAIL test (marked as expected to fail)

**Verdict:** `eligible: False`.

An `xfail`-decorated test produces an `XFAIL` outcome in pytest output, which
the gate classifies as non-passing. This is intentional: `xfail` indicates that
the behavior is known-broken. Wrapping a failing test in `@pytest.mark.xfail`
does not satisfy the done gate — the underlying failure still blocks eligibility.
This closes the xfail-masking loophole where a developer marks a test `xfail` to
make CI green while leaving the AC unimplemented.

### Skipped test

**Verdict:** `eligible: False`.

A `SKIPPED` outcome — from `@pytest.mark.skip`, `pytest.skip()`, or a
`skipif` condition that evaluated to true — counts as non-passing. If a test is
skipped because its environment dependency is unavailable, the AC is not
provably done in that environment. Resolve the dependency or make the test
runnable before marking the AC done.

### XPASS test (unexpectedly passed)

**Verdict:** `eligible: False`.

An `xpass` outcome arises when a test decorated `@pytest.mark.xfail` passes
unexpectedly. The gate treats `XPASS` as non-passing. Remove the `xfail`
decoration and confirm the test produces a clean `PASSED` before the gate
will accept it.

### Pytest timeout or subprocess error

**Verdict:** `eligible: False` (the gate returns an empty pytest result map,
which causes every linked test to be classified as non-passing).

If the 60-second timeout expires or the subprocess cannot start, the gate
logs a warning to stderr and treats the run as a complete failure. Fix the
environment (import cycles, missing dependencies, slow setup) so the linked
test files complete within the timeout.

---

## 4. Dangling tags

Every time the gate runs for any `ac_id`, it also scans the entire test tree
for `# covers:` tags whose target id is **not an active AC in the store**. A
tag is dangling when either of these conditions holds:

- The AC id is absent from the store (no YAML file found for that id).
- The AC's YAML file exists but its `status` field is not `"active"` (e.g.
  `deprecated`, `superseded`, or any other non-active value).

Dangling tags are reported as a `dangling_tags` list in the verdict, where
each entry is a dict with keys `id` (the AC id) and `location` (the file path
and line number of the first occurrence). When the same dangling id appears in
multiple places, only the first occurrence is reported.

**Dangling tags are informative, not blocking.** They do not prevent the done
verdict for the AC being queried. They flag housekeeping work: either the test
should be retagged to an active AC, or the tag should be removed if the
covering relationship no longer exists.

Common causes of dangling tags:

- An AC was retired or superseded and the test file was not updated.
- The AC id in the tag has a typo (e.g. `BO-2400a-01` instead of `BO-2400a-1`).
- The test was authored before the AC was written and used a placeholder id.

---

## Verification

After tagging your test, confirm the gate would pass before committing:

```bash
python /home/henzeh/projects/leafcutter/leafcutter-ai/scripts/ac_store/done_proof.py
```

(The exact invocation depends on how the gate script is wired in your install —
see [done-proof-enforcement.md](done-proof-enforcement.md) for the command-line
interface and the pre-commit hook that runs it automatically.)

To confirm the tag was picked up, search for the id in the test tree:

```bash
grep -rn "covers: <AC-ID>" unit_tests/
```

Expected output: one or more lines showing the file, line number, and tag text.
If the grep returns nothing, the tag is missing or malformed — re-check the
placement rules in [Section 1](#1-adding-a-covers-tag).

---

## The mechanical gate is the arbiter

Human review of a test function cannot substitute for the gate. The gate checks
the exact pytest outcome at the moment of the commit — not a developer's
recollection that "the tests were green earlier." The pre-commit hook blocks the
commit when any linked test is non-passing; the CI job blocks the PR merge for
the same reason.

This design is intentional: xfail-masking, stale tests, and optimistic
self-assessments are the most common sources of phantom-done ACs in this project.
By requiring the gate to pass on every commit, the linkage is enforced continuously
rather than at a single point-in-time review.

For the full enforcement configuration — hook name, CI job name, and how to
inspect gate output — see [done-proof-enforcement.md](done-proof-enforcement.md).
