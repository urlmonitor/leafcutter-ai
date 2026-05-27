# How to Write a TDD Ticket

This guide walks you through writing a ticket that will go through the leafcutter
TDD flow: `test-writer` (writes failing tests) → `python-coder` (makes them green).

For background on why this flow exists, see
[docs/explanation/tdd-workflow.md](../explanation/tdd-workflow.md) and
[ADR-004](../architecture/adrs/ADR-004-tdd-workflow-enforcement.md).

---

## Step 1: Populate `## Test Requirements` (or ensure test-planner will)

The TDD flow depends on the `## Test Requirements` block being present in your
ticket body and populated with at least one test entry. This block is authored
during the business analysis (BA) flow by `test-planner`.

If you are writing a ticket manually (without running `/create-ticket`), ensure
the `## Test Requirements` block exists and has entries:

```yaml
## Test Requirements

tests:
  - test_name: test_foo_raises_on_empty_input
    target_dir: unit_tests/my_module/
    type: unit
    covers: "MyClass.foo() raises ValueError when input is empty"
    db_required: false
```

**If your ticket is docs-only or config-only** (no Python code changes), set
`tests: []` and set `test-writer: not_needed` in the `agents:` frontmatter.
See the FAQ below.

## Step 2: Understand What test-writer Will Do

When `test-writer` runs (at priority 5, before coders):

1. It reads your `## Test Requirements` block.
2. It writes failing test stubs to the `target_dir` paths you specified.
3. It runs the new tests to confirm they are **red** (non-zero exit).
4. It records the failures in a `red_baseline` block in its sign-off comment.

The tests MUST be red after `test-writer` runs. If all tests pass immediately
(before any implementation), that means the tests are under-specified — they are
not actually verifying the spec. `test-writer` will flag this and add stronger
assertions.

## Step 3: What Happens When the Coder Runs

`python-coder` runs at priority 6, after `test-writer`. Before writing any code, it:

1. Reads the `red_baseline` block from `test-writer`'s sign-off comment.
2. Uses those test names as its done criterion: **all `red_baseline` tests must be
   green, and no previously-passing test may be red**.
3. Writes production code to satisfy the tests.
4. Documents which `red_baseline` tests it turned green in its sign-off comment.

You do not need to tell the coder what to implement in exhaustive detail — the
failing tests are the specification. This is why the `## Acceptance Criteria`
Gherkin scenarios and the `## Test Requirements` tests should agree.

## Step 4: What the Contract-Shrinking Hook Catches

The `check_contract_shrinking.py` pre-commit hook blocks any commit where:
- A production `.py` file is modified **AND**
- A test-weakening pattern is present (test deletion, `pytest.skip`,
  `pytest.mark.xfail`, `@unittest.skip`, `@unittest.expectedFailure`).

When blocked, you will see:
```
[contract-shrinking guard] BLOCKED
Reason: Staged diff contains test-weakening changes concurrent with production code changes.
Violations detected:
  - unit_tests/my_module/test_foo.py: test function deleted at line 42

You may not delete, skip, or xfail tests while also modifying production code.
If a test is genuinely wrong, fix the test in a separate commit with no
production code changes.
See docs/how-to/writing-a-tdd-ticket.md for the full policy.
```

**If the hook fires during your coder's commit**, it means the coder tried to
silence a test rather than fix the underlying issue. The correct resolution is:
- Revert the test weakening.
- Fix the production code so the test passes legitimately.
- If the test is genuinely wrong (it tests the wrong thing), fix the test in a
  **separate commit** with no production code changes.

---

## FAQ

### What if test-planner left my tests array empty?

If `## Test Requirements` has `tests: []` or the block is absent, `test-writer`
is automatically skipped. The `ticket-supervisor` detects the empty array and
signs off `test-writer` with a skip note, then proceeds to the coder.

This is the correct behavior for docs-only and config-only tickets. If you have
a code ticket that accidentally has an empty `tests:` array, go back and populate
it before running `/build-feature`.

### What if a red_baseline test is genuinely wrong?

If a test in `red_baseline` is incorrect (it tests the wrong behavior, or it was
written based on a misunderstanding of the spec), fix it in a **separate commit**
with no production code changes.

The workflow:
1. Create a separate small commit: `fix(tests): correct test_foo assertion — spec
   says ValueError, not TypeError`.
2. No production code in this commit.
3. Then proceed with the implementation commit (production code only, no test changes).
4. The `check_contract_shrinking.py` hook allows pure test-change commits (step 1)
   and pure production-change commits (step 2) separately — it only blocks when both
   happen in the same commit.

### What if a coder cannot make a red_baseline test pass?

The coder must emit `(status: blocker)` rather than skip or delete the test. The
ticket-supervisor will escalate to the user. Possible resolutions:
- The test is wrong — fix it in a separate commit (see above).
- The implementation approach needs to change — the user decides.
- The ticket scope is incorrect — revise the ticket.

### Do I need test-writer for SQL tickets?

Not yet. SQL TDD ordering (test-first for SQL) is deferred to
`EPIC-SQLTDDEnforcement`. For SQL tickets, set `test-writer: not_needed` in the
`agents:` frontmatter. The `sql-coder` still has the contract-shrinking prohibition
(honor-system layer) — it will not weaken existing SQL tests.

### How do I set up a ticket for docs-only or config-only work?

In your ticket frontmatter:
```yaml
agents:
  architect-review: not_needed
  test-writer: not_needed      # docs-only — no test files to write
  python-coder: not_needed     # no Python code changes
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
```

And in the body, either omit `## Test Requirements` or write:
```yaml
## Test Requirements

tests: []
```

Both are equivalent. The ticket-supervisor will skip `test-writer` in either case.
