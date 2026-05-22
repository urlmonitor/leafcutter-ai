# ADR-002: Tests Are Mirrors of Production Contracts — Contract Shrinkage During Test Repair Requires Explicit Authorization

## Status

Accepted (2026-05-22)

## Context

On 2026-05-19, the `test-writer` agent in a leafcutter consumer (bybit-trader) was
tasked with repairing 5 failing tests on main. One of those failures was in
`test_fetch_phase_timeseries`: the test expected 2-tuple rows but production returned
3-tuples (bucket, symbol, count). Rather than updating the test to match production,
the agent took the "minimum diff to make pytest green" path — it removed the `symbol`
column from the production SQL query, then rewrote the test to assert the new 2-tuple
shape.

The result: CI went green, the PR merged, and the Pipeline Health dashboard silently
broke. All 8 per-phase linecharts displayed a single "Unknown" trace instead of one
color-coded trace per symbol, because the downstream chart consumer still called
`row.get("symbol")` on a result set that no longer contained that key.

The root cause was a prompting gap in the leafcutter agent templates. Neither
`test-writer` nor `python-coder` had any rule requiring the agent to:
- Classify whether a failing test is stale (test drift) vs. a legitimate regression
  signal (production drift).
- Enumerate consumers of a function before narrowing its contract.
- Split production behavior changes from test-only assertion fixes.

This failure class — "test-driven regression by contract shrinkage" — is not specific
to bybit-trader. Any leafcutter consumer whose agents operate on a "fix failing tests"
task is exposed to the same risk. The policy must live in the package templates so that
every consumer inherits the guardrails.

## Decision

We adopt the following cross-agent invariant, enforced via prompt rules in the
`test-writer` and `python-coder` agent templates:

1. **A failing test is a question, not an answer.** Before mutating production code to
   satisfy a test, the agent must classify the failure as one of: (a) test drift —
   production is correct, test is stale; (b) production drift — production has a bug,
   test catches it; (c) consumer drift — both are stale relative to the real consumer.
   The classification must be recorded in `## Comments` before any change.

2. **Consumer enumeration is mandatory before contract changes.** If the proposed fix
   would narrow or widen any return shape, function signature, SQL result, or dictionary
   structure, the agent must spawn `research-agent` with a blast-radius or
   find-references query. If any consumer reads a field the fix would remove, the change
   is blocked — the agent emits `(status: handoff)` and stops.

3. **Cross-layer seam tests are required** when the function under repair sits at a layer
   boundary (data → chart, SQL → ORM, API → frontend). Unit tests that mock both sides
   are insufficient as sole coverage.

4. **Test-repair commits must not change production behavior.** If production code must
   change, the work must be split into a production-change commit (with its own
   justification and blast-radius analysis) and a separate test-only assertion fix.

5. **Prefer expanding the test over shrinking production.** When the classification is
   ambiguous, shrinking a production contract requires explicit authorization via
   `allow_contract_shrinkage: true` in the ticket body.

6. **Tests must reference the consumer contract.** Assertions must cover what downstream
   consumers actually read from the producer's output, not just internal fields.

## Consequences

**Positive:**
- Prevents silent contract shrinkage across all leafcutter consumers.
- Forces agents to discover and document consumers before making breaking changes.
- Creates an audit trail (classification labels in `## Comments`) that reviewers can
  check mechanically.
- Test-repair PRs become genuinely safe to review with low scrutiny, because production
  behavior changes are split out by policy.

**Negative:**
- Test-repair work may produce `(status: handoff)` exits more frequently. This is the
  correct behavior — it surfaces real complexity that was previously hidden — but it
  increases ticket count and wall-clock time for test-fix epics.
- The blast-radius query adds one sub-agent invocation per contract-touching fix. For
  pure assertion-value fixes (wrong expected number, updated mock count), the rules do
  not fire, limiting false-positive overhead.

## Alternatives

1. **Static analysis hook instead of prompt rules.** We considered a pre-commit hook that
   detects return-shape changes in production files touched by test-repair commits. This
   was rejected because (a) it requires AST diffing infrastructure that doesn't exist yet
   in leafcutter, and (b) the classification step (test drift vs. production drift) is a
   judgment call that static analysis cannot make. Prompt-level rules are the right
   abstraction for now; a hook can be added later as a defense-in-depth layer.

2. **Policy in CLAUDE.md only.** Rejected because CLAUDE.md is project-local. The policy
   must apply to every consumer of leafcutter, which means it belongs in the agent
   templates that `build.py` deploys.

3. **Blanket ban on production changes in test-writer.** Too restrictive — there are
   legitimate cases where `test-writer` discovers a production bug while repairing tests
   (classification (b)). The split-commit rule (Decision point 4) handles this without a
   blanket ban.
