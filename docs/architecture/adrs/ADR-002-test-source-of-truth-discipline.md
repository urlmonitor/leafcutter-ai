# ADR-002: Tests Are Mirrors of Production Contracts; Contract Shrinkage Requires Explicit Authorization

## Status

Accepted (2026-05-21)

## Context

On 2026-05-19, a test-repair commit in a leafcutter consumer (bybit-trader) silently narrowed the production contract of `fetch_phase_timeseries` by removing the `symbol` column from its SQL SELECT and GROUP BY clauses. The change was made to satisfy a stale test assertion that expected 2-tuples instead of 3-tuples. The test-writer agent treated the failing test as a specification and modified production code to match it, rather than recognizing that the test was stale and production was correct.

The downstream consumer (`_build_timeseries_figure`) still expected `row.get("symbol")` in each result row. With `symbol` removed, every row fell into the `"Unknown"` bucket, producing a single mislabelled trace per phase on the Pipeline Health dashboard.

This incident exposed a systemic gap in the leafcutter agent templates: no rule required agents to classify test failures before modifying production code, and no rule required consumer enumeration before narrowing a function's return shape.

### Root causes

1. **Tests treated as source of truth**: the agent changed production to satisfy the test, inverting the actual contract relationship.
2. **No blast-radius check**: no consumer enumeration was performed before removing the `symbol` field.
3. **No cross-layer integration test**: unit tests mocked both sides of the data-to-chart seam; nothing covered the boundary.
4. **Behavior change buried in a test-repair commit**: the commit message framed the change as "fix tests," giving reviewers no reason to suspect a runtime contract change.

## Decision

We adopt the following cross-agent policy, codified as the "Source-of-Truth Discipline" in agent templates:

**(a) A failing test is a question about which side has drifted.** The agent must classify the failure as one of: test drift (test stale, production correct), production drift (production buggy, test correct), or consumer drift (both sides stale relative to the real downstream consumer). The classification must be stated explicitly in `## Comments` before any change is made.

**(b) Consumer enumeration is mandatory before contract changes.** Before narrowing or widening the shape of any return value, function signature, SQL result, or dictionary structure, the agent must query `research-agent` for all consumers of the producing function and list them in `## Comments`. If any consumer reads a field the proposed change would remove, the change is blocked.

**(c) Contract shrinkage requires a separate commit/ticket.** Any narrowing of a production contract that has consumers must be split out of the test-repair work into its own commit or ticket with independent justification, blast-radius analysis, and sign-off.

**(d) `allow_contract_shrinkage: true` is the explicit authorization gate.** If a ticket body contains this flag, the agent may proceed with a contract-narrowing change after completing consumer enumeration and documenting the impact. Without this flag, the agent must assume the test is stale and restore it to match the existing production contract.

**(e) Cross-layer seam tests are mandatory at layer boundaries.** When the function under repair sits at a layer boundary (data → chart, SQL → ORM, API → frontend), at least one integration-style test must pipe representative producer output directly into the consumer and assert observable behavior.

## Consequences

**Positive:**
- Test-repair commits can no longer silently narrow production contracts across any leafcutter consumer.
- Agents are forced to consult downstream consumers before modifying return shapes, catching regressions that unit tests alone would miss.
- The classification step creates an audit trail in ticket comments that reviewers can verify.

**Negative:**
- Test-repair work may produce `(status: handoff)` exits more frequently, requiring human review. This is the intended behavior — the prior failure mode was silent breakage, which is strictly worse.
- Agents will occasionally spend additional time on blast-radius queries for changes that turn out to be safe. The cost of a false positive (one extra query) is far lower than a false negative (broken dashboard).

## Alternatives

1. **Rely on PR review to catch contract shrinkage.** Rejected — the May-19 incident passed PR review because test-repair PRs are assumed to be production-no-ops.
2. **Add integration tests only, without agent prompting changes.** Rejected — integration tests at the seam would have caught this specific incident but would not prevent the general class of "test-driven contract shrinkage" across arbitrary function boundaries.
3. **Block all production changes in test-repair tasks.** Rejected as too restrictive — some test failures genuinely indicate production bugs (classification (b)), and blocking those would force unnecessary ticket splits.
