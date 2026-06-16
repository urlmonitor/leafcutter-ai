# TDD Workflow in the Leafcutter Agentic Build Pipeline

This explanation describes how Test-Driven Development works inside leafcutter's
agentic build pipeline — specifically how it differs from classical TDD with a
human at the keyboard, why it was designed this way, and what the enforcement
layers look like.

See [ADR-004](../architecture/adrs/ADR-004-tdd-workflow-enforcement.md) for the
architectural decision record that formally adopted this approach.
See [docs/how-to/writing-a-tdd-ticket.md](../how-to/writing-a-tdd-ticket.md) for
the step-by-step guide on writing a ticket that goes through TDD flow.

---

## What "Test-First in an Agentic Pipeline" Means

Classical TDD has a human developer: (1) write a failing test, (2) write minimal
code to make it pass, (3) refactor. The human holds context across all three steps.

In an agentic pipeline, each step is executed by a different sub-agent. There is
no persistent human context between steps. This creates a problem: if the test
agent runs after the coder agent, the tests describe what the code does — not
what the ticket says it should do. Tests become post-hoc documentation rather than
a design specification.

The leafcutter TDD workflow solves this by dispatching agents in the correct order:

```
architect-review (4) → test-writer (5) → python-coder (6) → test-runner (9)
```

`test-writer` runs before `python-coder`. The tests it writes are failing because
the production code does not exist yet. This is the correct red-green cycle — even
in an agentic context.

---

## The Three Phases

### Phase 1: BA flow populates Test Requirements (before the build epic starts)

During the business analysis (BA) flow, `business-analyst` reads the ticket's
`## Acceptance Criteria` and populates the `## Test Requirements` block. This
block specifies:
- What test files to write and where
- What scenarios each test should cover
- Whether a database connection is needed

The `## Test Requirements` block is the handoff from BA flow to build flow.
`test-writer` reads it; the ticket author does not need to write test code manually.

### Phase 2: test-writer (build flow, red)

`test-writer` runs at priority 5, before any coder. It:
1. Reads `## Test Requirements` to understand what to test.
2. Writes failing test stubs that assert the spec.
3. Runs the new tests to confirm they are **red** (non-zero exit code).
4. Captures a `red_baseline` block in its sign-off comment.

The `red_baseline` is a YAML block listing every new test, its file path, and the
exact error seen when it fails:

```yaml
red_baseline:
  - test_name: test_check_contract_shrinking_blocks
    file: unit_tests/commit_guardian/test_contract_shrinking.py
    error: "AssertionError: 2 != 1 (hook script not found)"
```

The tests must be red. If all tests pass immediately (before any implementation
exists), the tests are under-specified — they do not actually verify the spec.

### Phase 3: python-coder (build flow, green)

`python-coder` runs after `test-writer`. It:
1. Reads the `red_baseline` block from `test-writer`'s sign-off comment.
2. Writes production code to make every listed test green.
3. Runs the test suite to confirm the `red_baseline` tests now pass.
4. Confirms no previously-passing test has been broken.
5. Documents the results in its sign-off comment.

The `red_baseline` is the coder's explicit done criterion — it is machine-verifiable
rather than subjective.

---

## The red_baseline Concept

The `red_baseline` is more than a test list. It is a formal handoff artifact:

- **For the coder**: a checklist of exactly what must be made green. No ambiguity.
- **For the ticket**: a durable record in `## Comments` of the spec at the time
  tests were written (before any implementation bias entered).
- **For reviewers**: evidence that tests were written before the code, not after.
- **For the contract-shrinking guard**: a reference to compare against — if the
  coder tried to make these tests "green" by skipping or deleting them, the guard
  blocks the commit.

---

## The Three-Layer Contract-Shrinking Guard

"Contract shrinking" is the failure mode where a test is silenced (deleted, skipped,
or marked xfail) instead of the underlying code being fixed. This is a critical
violation because it makes the CI green while hiding a regression.

Three layers enforce the contract:

### Layer 1: Pre-commit hook (blocking)

`check_contract_shrinking.py` runs as a pre-commit hook. It scans the staged diff
and blocks any commit where **both** of the following are true:
- A production `.py` file is modified.
- A test-weakening pattern is present (test deletion, `pytest.skip`, `pytest.mark.xfail`,
  `@unittest.skip`, `@unittest.expectedFailure`).

If only test changes are staged (no production code changes), the hook passes —
this allows legitimate test refactoring in a separate commit.

When blocked, the hook prints:
```
[contract-shrinking guard] BLOCKED
Reason: Staged diff contains test-weakening changes concurrent with production code changes.
...
```

### Layer 2: Supervisor-side warn (advisory)

After any coder signs off, the `ticket-supervisor` runs a post-coder diff check
for weakening patterns. If patterns are detected, it appends a
`contract-shrinking-warning` comment to the ticket. This is informational — the
pipeline continues, but the warning is visible in the ticket history. The pre-commit
hook is the blocker; this is the audit trail.

### Layer 3: Honor-system clause (in agent definitions)

`python-coder.md` and `sql-coder.md` both contain an explicit prohibition:

> "You MUST NOT delete, comment out, add pytest.skip, pytest.mark.xfail,
> @unittest.skip, @unittest.expectedFailure, if False: wrappers, or any equivalent
> skip/xfail mechanism to any test in order to make the suite pass. Weakening the
> test suite to achieve a green run is a critical violation."

If a coder cannot make a `red_baseline` test pass with correct implementation, it
must append `(status: blocker)` — not weaken the test.

---

## The Docs-Only / Config-Only Skip Rule

Not every ticket produces Python code. Documentation tickets, config-only tickets,
and schema migration tickets that have no logic layer do not need test-writer to run.

The skip rule: if a ticket's `## Test Requirements` block is absent or has
`tests: []` (empty array), `test-writer` signs off immediately with zero file
writes and appends:

```
test_requirements empty — skipping test-writer phase (docs/config-only ticket)
```

The `ticket-supervisor` also implements this check — it reads the `tests:` array
before dispatching `test-writer` and skips the dispatch if the array is empty or
absent. This prevents docs PRs from stalling at the test-writer phase.

Ticket authors who know upfront that no tests are needed should set
`test-writer: not_needed` in the `agents:` frontmatter map. This avoids even the
dispatch check.

---

## Scope: Python Only in Phase 1

This TDD workflow currently applies to Python code only. SQL TDD ordering
(where `sql-test-writer` would run at priority 5, before `sql-coder`) is deferred
to a follow-on epic (`EPIC-SQLTDDEnforcement`). The SQL contract-shrinking
prohibition (honor-system layer) is active, but the test-first sequencing is not
yet enforced for SQL.
