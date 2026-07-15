# BO-1700 Implementation Audit — 2026-07-14

Scope: the 12 ACs the pr-reviewer flagged on ticket `01_bo1700_test_coverage.md`
as "missing covers: tags". Method: ac-audit skill (Stage 1 grep evidence map,
Stage 2 green-test run, Stage 3 skeptical per-AC deep verification).

## Executive summary

The pr-reviewer's "12 ACs missing covers: tags" was both **partly wrong** (some
ACs are genuinely covered — just in test files the pr-reviewer never inspected,
because the ticket's `files_touched`/test-runner only exercised
`test_verify_precommit_active.py`) and **understated** (the real problem is worse
than tags: a red test, phantom existence-only tests, and mistagged coverage
shipped to main in a *test-coverage* epic).

Verdict counts (12 ACs): COVERED_TAGGED 1 · COVERED_UNTAGGED 3 ·
TESTABLE_UNCOVERED 7 · NON_TESTABLE 1.

Stage 2: the cited BO-1700 test files run green (73 passed) — the coverage that
does exist is real, not xfail-masked.

## Per-AC verdicts

| AC | Testable | Verdict | Real assertion in | Action |
|---|---|---|---|---|
| BO-1700e-1 | yes | COVERED_TAGGED | test_build_deployment.py::test_ac_build_deploys_all_3_guard_scripts | none — done |
| BO-1700c-1 | yes | COVERED_UNTAGGED | test_ensure_precommit_config.py (TestManifestIndex0, TestConfigAlreadyExistsSubprocess) | retag `UNKNOWN`→BO-1700c-1 |
| BO-1700c-1-iv | yes | COVERED_UNTAGGED | test_ensure_precommit_config.py (TestAtomicityPartialFailureCleanState, TestIdempotencyCallTwice) | retag `UNKNOWN`→BO-1700c-1-iv |
| BO-1700d-1 | yes | COVERED_UNTAGGED | test_setup_ticket_worktree.py (TestBootstrapPreDriveGate ×4) | retag `UNKNOWN`→BO-1700d-1 |
| BO-1700c-1-i | yes | TESTABLE_UNCOVERED | none (test is RED) | fix mispathed test (`_find_main_tree_root` resolves real workspace `.leafcutter`, not fixture) |
| BO-1700c-1-ii | yes | TESTABLE_UNCOVERED | none (existence-only) | replace `hasattr` phantom with a real exit-1/loud-error assertion |
| BO-1700e-2 | yes | TESTABLE_UNCOVERED | none | assert git-common-dir resolver in run_hook.py |
| BO-1700e-4 | yes | TESTABLE_UNCOVERED | none (partial) | assert 4 checks pass / no false chain-broken in a plain clone |
| BO-1700e-5 | yes | TESTABLE_UNCOVERED | none (mistagged, ~opposite) | assert main-tree IS gated (not just graceful-skip-when-uninstalled) |
| BO-1700f-1 | yes | TESTABLE_UNCOVERED | none (mistagged) | assert no-config → INFO + exit-0 path |
| BO-1700f-1-i | yes | TESTABLE_UNCOVERED | none (docstring only) | assert hard-fail-naming-worktree silent-skip bug fix |
| BO-1700d-4 | no | NON_TESTABLE | none | drop from unit-test ac_coverage (sequence-diagram surface, doc_link status: planned) |

## Phantom-done risk — called out

- **RED test shipped to main:** `test_ensure_precommit_config.py::test_config_missing_symlink_fails_copy_succeeds`
  (BO-1700c-1-i) fails — `ensure_config._find_main_tree_root` resolves the real
  workspace root instead of the test fixture main_tree. The ticket's single-file
  test-runner (only `test_verify_precommit_active.py`) never surfaced it.
- **Existence-only phantom tests:** BO-1700c-1-ii and a c-1 symlink-success test
  assert only `hasattr(...)` — green while asserting no behavior.
- **Mistagged coverage:** BO-1700e-5 / f-1 / f-1-i carry `# covers:` tags on tests
  that assert unrelated behavior (graceful-skip / idempotency / byte-identity),
  masking real gaps.

## Remediation plan

1. **Retag (3, mechanical):** c-1, c-1-iv, d-1 — `# covers: UNKNOWN` → AC id.
2. **Drop (1):** d-4 from ticket 01 `ac_coverage` (non-testable diagram surface).
3. **Author/fix real tests (7):** c-1-i (fix red mispathed test), c-1-ii (real
   assertion), e-2, e-4, e-5, f-1, f-1-i.
4. Mark evidence-anchored ACs done (`covered_by` = real test), re-run pr-reviewer,
   set ticket 01 done, archive epic — all via an isolated worktree + PR off
   origin/main (main is PR-only).
