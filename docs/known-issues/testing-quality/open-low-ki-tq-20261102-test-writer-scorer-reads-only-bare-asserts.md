---
title: "KI-TQ-20261102-test-writer-scorer-reads-only-bare-asserts — two test-writer static scorer kinds read only bare `assert` statements, so a unittest test that asserts the right thing with `self.assertEqual` is scored falsely red"
description: "medium — scripts/evals/produced_tests_scoring.py counts_rows_and_non_null and asserts_known_seeded_value walk only ast.Assert nodes, and _count_side also wants an int literal on the right of a count. The test-writer template steers the agent to unittest.TestCase, so self.assertEqual(len(volumes), len(window)) and self.assertEqual(result[\"AAPL\"], 190.12) are invisible. Live runs 2026-11-02: empty-window failed counts_rows_and_non_null twice, presence-is-not-correctness failed asserts_known_seeded_value three times, each on a test that asserts exactly what the kind asks for."
type: reference
category: reference
status: active
created: '2026-11-02'
last_updated: '2026-11-02'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
  - docs/reference/produced-tests-eval-assertion-kinds-test-writer.md
  - docs/known-issues/testing-quality/open-low-ki-tq-20261102-test-writer-rows-check-unrequested-report-wording.md
---

# KI-TQ-20261102-test-writer-scorer-reads-only-bare-asserts — unittest assertions are invisible to two test-writer scorer kinds

> Filed 2026-11-02. Index: [testing-quality.md](../testing-quality.md). Filename severity is the
> three-level index bucket (`low`); the original grading is the `**Severity:**` line below.

- **Severity:** medium. The scorer marks a correct test as wrong (falsely red) on two of the eight
  test-writer rows, so the live test-writer score understates the agent and a fix to the agent
  cannot be measured on these rows.
- **Status:** open, no AC.
- **Occurrences:** 5 failed assertions in three live runs on 2026-11-02 (Windows 11, main
  `8248ac7a`): `counts_rows_and_non_null` on `empty-window` in the first live run and re-run 1
  (re-run 2 passed because the agent happened to write bare `assert` statements);
  `asserts_known_seeded_value` on `presence-is-not-correctness` in all three runs.
- **First seen:** 2026-11-02 · **Last seen:** 2026-11-02
- **Where:** `scripts/evals/produced_tests_scoring.py` (line numbers on `171aafa5d`, unchanged since
  `8248ac7a`): `_count_side` :87-94, `_count_kind` :97-108, `counts_rows_and_non_null` :111-121,
  `asserts_known_seeded_value` :130-141; rows `empty-window` and `presence-is-not-correctness` in
  `scripts/evals/sets/test-writer.jsonl` (lines 3 and 4).

## Symptom

A live test-writer run writes a `unittest.TestCase` test that asserts an exact row count, an exact
non-`None` count, or equality with a value the test itself seeded, and the row fails with "the test
asserts no an exact processed-row count and no a non-NULL count" or "no assertion compares against
a value the fixture seeded; the test measures presence, not correctness".

## Mechanism

- `counts_rows_and_non_null` collects candidates with `ast.walk(tree)` filtered to `ast.Assert`
  (:117). A method call such as `self.assertEqual(a, b)` is an `ast.Expr` around an `ast.Call`, so
  it is never looked at.
- Even as a bare `assert`, `_count_side` (:90) accepts a count only when the right-hand side is an
  `int` literal; `assert len(volumes) == len(window)` would still be rejected, although comparing
  against the length of the seeded input is the stronger, non-magic form of an exact count.
- `asserts_known_seeded_value` likewise walks only `ast.Assert` nodes (:136). The seed side already
  reads constants from any assignment (`_numbers` :124-127), so `feed = {"AAPL": 190.12, ...}` is a
  seed; only the assertion side misses `self.assertEqual(result["AAPL"], 190.12)`.
- The test-writer template steers the agent to unittest: Step 2a says `framework: "unittest"` →
  use `unittest.TestCase` (`templates/agents/test-writer.md`:824), and both code examples are
  `unittest.TestCase` classes (:844, :880). The `empty-window` and `presence-is-not-correctness`
  fixtures carry no `skills_config.json`, so the agent falls back on those examples.
- The sql-test-writer twin of this kind already reads `assertEqual` / `assertEquals`
  (`scripts/evals/sql_test_writer_eval/evidence_kinds.py` `_equality_statements` :79-87) and accepts
  a non-literal right side, which is why re-runs 3 and 4 of `empty-window-database-shape` passed
  with `self.assertEqual(len(rows), len(seeded))`.

## Evidence

Kept outputs (local to the run machine, not committed):
`<session scratchpad>/kept_runs/`
(`run1` = re-run 1, `run2` = re-run 2; first live run results in `../rerun_score/test-writer.json`).

- `run1/test-writer/empty-window/files/test_buy_volume_window.py`:22-23:
  `self.assertEqual(len(volumes), len(window))` and
  `self.assertEqual(sum(v is not None for v in volumes), len(window))` — exactly the exact-row and
  non-`None` counts the kind asks for. Result: `counts_rows_and_non_null` failed ("the test asserts
  no an exact processed-row count and no a non-NULL count"); `produced_test_green` and
  `fails_on_mutants` passed (both mutants killed).
- `run2/test-writer/empty-window/files/test_buy_volume_window.py`:22-23 wrote
  `assert len(volumes) == 3` / `assert sum(v is not None for v in volumes) == 3` and passed the
  same kind: the outcome depends on assertion style, not on what is asserted.
- `run1/test-writer/presence-is-not-correctness/files/test_live_value_presence.py`:10 seeds
  `feed = {"AAPL": 190.12, "MSFT": 410.55, "TSLA": 248.50}` and :19-21 assert
  `self.assertEqual(result["AAPL"], 190.12)` (and the other two). `run2/.../test_live_value_presence.py`
  :11 and :19-21 do the same with `150.25`. Both failed `asserts_known_seeded_value`; both passed
  `fails_on_mutants` against `constant_per_symbol.py` and `first_value_for_all.py`.

**Agent-side weakness seen on the same rows (not a scorer defect).** On `empty-window` and
`presence-is-not-correctness` the test-writer reports in both re-runs skip the template's
Completion Report format (`templates/agents/test-writer.md`:1171-1201: Tests Written, Verification
Run, the Three Questions table, "Wrong versions the tests now catch"); they are short prose
summaries. These two row inputs, unlike `refresh-gate` and `missing-setting-database-work`, do not
say "End with your completion report", and no assertion on any row checks for the format, so the
omission is invisible to the score. See also
[KI-TQ-20261102-test-writer-rows-check-unrequested-report-wording](open-low-ki-tq-20261102-test-writer-rows-check-unrequested-report-wording.md).

## Fix direction

- In both kinds, read unittest assertion calls as well as bare `assert`: `assertEqual` /
  `assertEquals` (as `_equality_statements` already does on the sql side), and for the count kind
  `assertGreater` / `assertGreaterEqual` with the same bound rules as `>` / `>=`.
- For an exact count, accept a non-literal integer expression on the other side (`len(seed)`,
  `len(window)`, a name assigned from one), not only an `int` literal.
- Update the `counts_rows_and_non_null` and `asserts_known_seeded_value` entries in
  `docs/reference/produced-tests-eval-assertion-kinds-test-writer.md` (:58-83, :85 onward), whose
  "Passes when" text says "an `assert`", and add a unittest passing example.
- Optionally add an assertion (or row) that checks the Completion Report sections, if the format
  is meant to be scored.
