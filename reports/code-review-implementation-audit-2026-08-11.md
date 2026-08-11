# code-review — implementation & test-coverage audit (2026-08-11)

Scope: `docs/acceptance-criteria/code-review/` (component `code-review`, CR-100 tree).
Method: ac-audit skill — Stage 1 mechanical evidence map, Stage 2 green-test run,
Stage 3 skeptical per-AC verification.

## Executive summary

| Verdict | Count |
|---------|-------|
| Behavioral leaves covered by a **green** test | 16 / 16 |
| Documentation ACs covered (deliverable written + test) | 6 / 6 |
| Leaf ACs total covered | 22 / 22 |

> Update (same day): the 6 documentation deliverables were subsequently authored and each
> covered by a test; the audit engine now reports `NOT_IMPLEMENTED: 0`, all 22 leaves covered.
> The "documentation ACs uncovered" section below is retained as the original finding.

- **No phantom-done.** The Stage-3 skeptic found no opposite-asserting, dead, xfail-masked,
  or mis-pathed tests. All 16 behavioral leaves are covered by real green tests in
  `unit_tests/test_code_smell_review_wiring.py` that parse the actual registry/skill files.
- The Stage-1 `TEST_NO_CODE` verdict on the 16 behavioral leaves is a **grep artifact**, not a
  gap: the audit engine looks for the AC id embedded in `scripts/`/`templates/`/`config/`, but
  prompt/registry artifacts (SKILL.md, JSON registries) don't embed AC ids. Coverage is via the
  test, confirmed green.
- After the audit, 5 initially-WEAK tests were **strengthened** (a-3, c-1, d-2, e-1-i) from
  substring checks to structural assertions; all 17 tests remain green + ruff-clean.

## Behavioral leaves (16) — covered, green

CR-100a-1, a-2, a-3, b-1, c-1, d-1, d-2, e-1, e-1-i, f-1, f-1-i, f-2, f-3, f-3-i, f-4, f-5
→ each `# covers:`-tagged in `unit_tests/test_code_smell_review_wiring.py`, all PASSED.

Coverage boundary (documented, honest): the *runtime* fan-out, the merge, and the depth-1
dispatch cannot be exercised in pytest (no agent spawning). Those ACs assert the
prompt/registry-level guarantee; runtime behavior was validated manually in-session.

## Documentation ACs (6) — NOT covered (deliverable unwritten)

| AC | Deliverable | Status |
|----|-------------|--------|
| CR-100a-4 | Reference doc: finding anatomy + Modern-12 catalogue | todo, no doc, no test |
| CR-100d-3 | Reference doc: severity rubric + report format | todo, no doc, no test |
| CR-100e-2 | How-to: running /code-smell-review | todo, no doc, no test |
| CR-100e-3 | Sequence diagram: invocation → report | todo, no doc, no test |
| CR-100f-6 | Component diagram: core/buckets/agents/orchestration | todo, no doc, no test |
| CR-100f-7 | Sequence diagram: parallel fan-out + merge | todo, no doc, no test |

These are `test_required: false` (a documentation class verified by `documentation-verifier`,
not unit tests). They are honestly `work_status: todo` — no phantom-done. Covering them
requires authoring the deliverables (which were out of the ACs+tests+ADR+changelog scope).

## Phantom-done risk

None found for the behavioral set. The only outstanding items are the 6 documentation
deliverables above, which are tracked not-done rather than falsely claimed.
