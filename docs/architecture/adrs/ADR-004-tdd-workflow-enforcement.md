# ADR-004: Test-First Workflow Enforcement in the Agentic Build Pipeline

## Status

Accepted (2026-05-27)

## Context

The leafcutter build pipeline dispatches agents in priority order. Before this
ADR, `test-writer` ran at **priority 8** — after `python-coder` (priority 6) and
`sql-coder` (priority 7). This is test-AFTER: coders write whatever implementation
they choose, and test-writer retroactively documents the behavior in tests.

Test-AFTER has several failure modes observed in practice:

1. **Tests confirm the implementation, not the spec.** When test-writer sees finished
   code, it writes tests that describe what the code does — not what the ticket's
   `## Acceptance Criteria` says it should do. Tests become documentation of the
   implementation rather than a specification check.

2. **The contract-shrinking problem (ADR-003 precursor).** Coders under time pressure
   narrow production contracts to "fix" a failing test. ADR-003 (2026-05-22) added
   rules to prevent this, but those rules depend on test-writer catching the narrowing
   during repair. With test-AFTER, test-writer is not present when the narrowing occurs.

3. **No machine-verifiable done criterion for coders.** "Write the implementation" has
   no clear stopping point. Coders that self-assess completion may ship code that
   satisfies partial spec or introduces subtle API drift.

4. **Contract shrinkage via skip/xfail.** When a test-AFTER test failed unexpectedly,
   coders would occasionally add `pytest.skip` or `pytest.mark.xfail` to suppress it
   rather than fix the underlying issue. The skip was then committed alongside
   production code changes, defeating the test's purpose.

## Decision

Flip `test-writer` to **priority 5** (from 8), running it BEFORE `python-coder`
and `sql-coder`. This is documented in `config/agent_registry.json`:

```json
{
  "id": "test-writer",
  "priority": 5,
  "priority_rationale": "Writes failing tests before coders implement; ensures tests exist and are red before any production code is written"
}
```

The TDD phase ordering is now:

```
architect-review (4) → test-writer (5) → python-coder (6) → sql-coder (7) → test-runner (9)
```

### The red_baseline contract

When `test-writer` runs, it:
1. Reads the ticket's `## Test Requirements` block.
2. Writes failing test stubs that assert the spec (not the implementation).
3. Runs the new tests to confirm they are red (non-zero exit).
4. Captures a structured `red_baseline` block in its sign-off comment:
   ```yaml
   red_baseline:
     - test_name: test_foo_raises_on_empty_input
       file: unit_tests/my_module/test_foo.py
       error: "AssertionError: expected ValueError, got None"
   ```

Coders use `red_baseline` as their explicit done criterion: all listed tests must
be green, and no previously-passing test may now be red.

### Three-layer contract-shrinking guard

To prevent coders from weakening tests to achieve a green run, three layers enforce
the contract:

1. **Pre-commit hook** (`check_contract_shrinking.py`, priority 5 enforcement):
   Blocks any commit where test-weakening patterns (deletion, skip, xfail) appear
   alongside production code changes. Exit non-zero with a human-readable error.
   See `templates/commit-guardian/check_contract_shrinking.py`.

2. **Supervisor-side warn** (`ticket-supervisor` post-coder check):
   After any coder signs off, the ticket-supervisor runs a diff-based check for
   weakening patterns and appends a `contract-shrinking-warning` comment to the
   ticket. This is advisory (does not block the pipeline) — the hook is the blocker.
   See `templates/agents/ticket-supervisor.md` §Post-coder contract-shrinking check.

3. **Honor-system clause** in agent definitions:
   `python-coder.md` and `sql-coder.md` explicitly prohibit skip/xfail/delete as
   a path to a green run. Agents that cannot make a `red_baseline` test pass must
   emit `(status: blocker)` rather than weaken the test.
   See `templates/agents/python-coder.md` §Contract-shrinking prohibition.

### Docs-only / config-only skip rule

For tickets that produce no Python code (documentation, configuration, schema
migrations without logic), `test-writer` would have nothing to write. The skip
rule prevents stalls: if the ticket's `## Test Requirements` block is absent or
`tests: []`, `test-writer` signs off immediately with a skip note and zero file
writes. This is implemented in both the `test-writer` agent definition and the
`ticket-supervisor` dispatch loop.

## Scope

This ADR covers Python-only TDD enforcement in Phase 1. SQL TDD ordering
(running `sql-test-writer` before `sql-coder`) is deferred to a follow-on epic
(`EPIC-SQLTDDEnforcement`, see ticket 08 of this epic). The `sql-coder` definition
is updated with the contract-shrinking prohibition (honor-system layer) but its
priority ordering relative to `sql-test-writer` is unchanged.

## Alternatives Considered

### Keep test-AFTER, add stronger PR review

PR review is subjective and asynchronous. A reviewer who approves a skip/xfail
without understanding the red_baseline context perpetuates the problem. Machine
enforcement (the hook) does not have this weakness.

### Add a separate "design" phase agent before coders

A dedicated design-phase agent would add complexity without adding value: the
`test-writer` agent in TDD mode already functions as the design artifact producer.
The test stubs ARE the design document.

### Honor-system only (no hook)

Honor-system clauses in agent definitions erode under time pressure. The ADR-003
incident (see Context) showed that a well-intentioned agent will take the path of
least resistance when under pressure. The hook closes this escape hatch.

## Consequences

### Positive

- Coders have a clear, machine-verifiable done criterion (make red_baseline green).
- Test quality improves: tests are written without knowledge of the implementation,
  so they test the spec rather than the code.
- Contract-shrinking is blocked at commit time, not discovered in post-merge review.
- The red_baseline is a durable artifact in the ticket's comment history.

### Negative / Trade-offs

- `test-writer` must complete before coders start — a sequential constraint that
  cannot be parallelized when both are in the same ticket.
- Some tickets will trigger the docs-only skip rule; ticket authors must ensure
  `## Test Requirements` is populated for code tickets (business-analyst does this
  during the BA flow).
- The hook may produce false positives on legitimate test refactor commits that
  coincidentally also include production code changes. The conjunction guard
  (both production AND weakening must be present) minimizes this; separate commits
  are the recommended resolution.

## References

- `EPIC-TDDWorkflowEnforcement` — the epic that implemented this decision
- `ADR-003-test-source-of-truth-discipline.md` — the precursor ADR that addressed
  contract shrinkage during test repair; this ADR is the structural enforcement
- `config/agent_registry.json` — source of truth for `test-writer` priority 5
- `templates/agents/test-writer.md` — agent definition implementing the red_baseline contract
- `templates/agents/python-coder.md` — TDD success gate + contract-shrinking prohibition
- `templates/commit-guardian/check_contract_shrinking.py` — pre-commit enforcement hook
- `docs/explanation/tdd-workflow.md` — narrative explanation of the TDD flow
- `docs/how-to/writing-a-tdd-ticket.md` — step-by-step guide for ticket authors
