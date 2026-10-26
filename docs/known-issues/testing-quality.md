---
title: "Known issues — testing-quality"
description: "Open, observed defects in the testing-quality component: the agent eval harness with its scoring and threshold gates, plus the test-isolation and verification-method defects that make a suite report the wrong answer — stale-module shadowing, incomplete fixtures, self-mirroring oracles, and verification that never asks what invokes the code. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: '2026-10-25'
components:
  - testing_quality
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/how-to/prove-ac-done.md
---


# Known issues — testing-quality

Observed defects in this component that are **not yet fixed**. This file exists so a
defect noticed in passing can be recorded in seconds, without authoring a full
acceptance criterion for something nobody has decided to build yet.

## How to use this file

**Read it before adding new capability to this component.** Fixing what is already
broken takes precedence over building more.

**Adding an issue.** Append a new `### KI-TQ-NNN` section using the next free number.
Nothing here is generated — edit it by hand. Fill in what you actually know; an issue
recorded with a thin `Evidence` line is far better than one not recorded.

**Hitting an existing issue.** Increment `Occurrences` and update `Last seen`. Do not
add a duplicate entry. Occurrences is an escalator, not the score — a blocker seen once
outranks an annoyance seen ten times.

**Severity** is `blocker` (work cannot land) / `high` (silent wrong behaviour) /
`medium` (real but survivable) / `low` (noise, dead code, cosmetics).

**Closing an issue.** When the fix lands, delete the section and reference the issue id
in the commit message. If it earns real work, author an AC for it and note the AC id in
`Status` — this file is a capture surface, not a replacement for the AC store.

---

## How this register is stored

This file is an **index**. Each known issue is its own file under [`testing-quality/`](testing-quality/), named `<status>-<severity>-<ki-id>.md`, so the directory listing answers "is anything open, and how bad" without opening anything:

```
ls docs/known-issues/testing-quality/open-blocker-*   # anything critical open?
ls docs/known-issues/testing-quality/open-*           # everything still live
```

Severity in the **filename** is a three-level index bucket (`blocker` / `high` / `low`). The original grading is preserved verbatim on each entry's own `**Severity:**` line — the bucket never overwrites it. `critical` indexes as `blocker`; `medium` indexes as `low`.

Fixed issues move to [`testing-quality/resolved/`](testing-quality/resolved/) and are no longer listed as open. They are kept, not deleted.

**Open: 38** (1 blocker, 15 high, 22 low) · **Resolved: 5** (recounted from the directory 2026-10-25, after KI-TQ-20261025-test-designer-eval-residual-gaps was filed)

## Open

| Severity | Issue | File |
|---|---|---|
| `blocker` | KI-TQ-007 — Six review rounds verified a component without once asking what invokes it | [open-blocker-ki-tq-007.md](testing-quality/open-blocker-ki-tq-007.md) |
| `high` | KI-TQ-001 — An unanswered eval row scores as an all-negative prediction, so a dead agent's floor is not zero | [open-high-ki-tq-001.md](testing-quality/open-high-ki-tq-001.md) |
| `high` | KI-TQ-002 — The CI eval job reports missing credentials as a low quality score | [open-high-ki-tq-002.md](testing-quality/open-high-ki-tq-002.md) |
| `high` | KI-TQ-004 — Bare-name `sys.modules` caching lets a stale deployed copy shadow the canonical module for a whole pytest session | [open-high-ki-tq-004.md](testing-quality/open-high-ki-tq-004.md) |
| `high` | KI-TQ-005 — Fixtures that never built the collection they assert over, three times in one epic | [open-high-ki-tq-005.md](testing-quality/open-high-ki-tq-005.md) |
| `high` | KI-TQ-006 — A matcher widening measured by its own author's grep: estimated one false positive, actual twenty-three | [open-high-ki-tq-006.md](testing-quality/open-high-ki-tq-006.md) |
| `high` | KI-TQ-010 — Nothing in the build pipeline asks whether a passing test is able to fail, and for a negative control that is the only question that matters | [open-high-ki-tq-010.md](testing-quality/open-high-ki-tq-010.md) |
| `high` | KI-TQ-011 — The AC xfail-masking plugin is disabled on the only gate that blocks, so a red baseline for a not-done AC is unmergeable — and where masking does apply it makes the local run exit 0 | [open-high-ki-tq-011.md](testing-quality/open-high-ki-tq-011.md) |
| `high` | KI-TQ-20260831-mutation-probe-lands-in-the-wrong-copy — a mutation proof injected into `templates/` proves nothing, because the tests import the build output — and it fails green | [open-high-ki-tq-20260831-mutation-probe-lands-in-the-wrong-copy.md](testing-quality/open-high-ki-tq-20260831-mutation-probe-lands-in-the-wrong-copy.md) |
| `high` | KI-TQ-20260901-1655 — A red-baseline gate cannot tell "red because the feature is missing" from "red because the test asserts against a stub defined in the test file", and the second kind is unsatisfiable — one of them blocked a completed seven-AC build | [open-high-ki-tq-20260901-1655.md](testing-quality/open-high-ki-tq-20260901-1655.md) |
| `high` | KI-TQ-20260907-agent-eval-gate-has-never-evaluated-an-agent — it fast-passes when nothing is affected and dies on a missing API key when something is | [open-high-ki-tq-20260907-agent-eval-gate-has-never-evaluated-an-agent.md](testing-quality/open-high-ki-tq-20260907-agent-eval-gate-has-never-evaluated-an-agent.md) |
| `high` | KI-TQ-20260908-0900 — The agent-eval harness reports "the CLI could not be launched" as a 22% quality score, and the pre-commit gate built on it cannot be satisfied in any fresh worktree | [open-high-ki-tq-20260908-0900.md](testing-quality/open-high-ki-tq-20260908-0900.md) |
| `high` | KI-TQ-20260914-1050 — the fast lane's green gate reports a pytest timeout as a list of failing test nodeids, so a budget overrun is indistinguishable from broken code — and the distinguishing machinery that exists for exactly this is discarded one layer below | [open-high-ki-tq-20260914-1050.md](testing-quality/open-high-ki-tq-20260914-1050.md) |
| `high` | KI-TQ-20260927-windows-local-runs-disagree-with-linux-ci — a fixed set of tests fails on an unmodified Windows checkout and passes on Linux CI, so a local red run cannot tell a regression from the baseline | [open-high-ki-tq-20260927-windows-local-runs-disagree-with-linux-ci.md](testing-quality/open-high-ki-tq-20260927-windows-local-runs-disagree-with-linux-ci.md) |
| `high` | KI-TQ-20261006-corpus-size-assertions-go-red-on-routine-authoring — six tests assert the size of this repository's own on-disk corpus against a hardcoded integer, so adding a decision record, mockup, mock dataset, changelog entry, flow or ticket turns them red with no defect present, and the failure is attributed to whatever PR is in flight | [open-high-ki-tq-20261006-corpus-size-assertions-go-red-on-routine-authoring.md](testing-quality/open-high-ki-tq-20261006-corpus-size-assertions-go-red-on-routine-authoring.md) |
| `high` | KI-TQ-20261009-integrity-plugin-prints-clean-while-failing-the-session — the shared-layout integrity plugin prints "clean" and exits 1 when a reader produced the layout after setup, and unittest-style readers have no documented way to request the fixture at setup | [open-high-ki-tq-20261009-integrity-plugin-prints-clean-while-failing-the-session.md](testing-quality/open-high-ki-tq-20261009-integrity-plugin-prints-clean-while-failing-the-session.md) |
| `low` | KI-TQ-003 — The eval staleness gate asks you to stage a file that is gitignored | [open-low-ki-tq-003.md](testing-quality/open-low-ki-tq-003.md) |
| `low` | KI-TQ-008 — A repository-global tree-purity guard false-positives under concurrent agents | [open-low-ki-tq-008.md](testing-quality/open-low-ki-tq-008.md) |
| `low` | KI-TQ-009 — A test-local oracle that duplicated the production bug it was written to detect | [open-low-ki-tq-009.md](testing-quality/open-low-ki-tq-009.md) |
| `low` | KI-TQ-013 — `git commit` in a temp fixture forks a background auto-gc, which races `rmtree` at teardown and fails the required CI suite at random | [open-low-ki-tq-013.md](testing-quality/open-low-ki-tq-013.md) |
| `low` | KI-TQ-20260907-0940 — A reachability fixture symlinks the package into its scratch workspace where the real consumer layout is a directory | [open-low-ki-tq-20260907-0940.md](testing-quality/open-low-ki-tq-20260907-0940.md) |
| `low` | KI-TQ-20260908-node-check-and-xfail-masking-agree-on-a-broken-script — `node --check` cannot prove the engine can load a workflow script, and a bare `pytest` on a not-done AC cannot distinguish pass from masked failure — together they nearly verified a script the engine could not run at all | [open-low-ki-tq-20260908-node-check-and-xfail-masking-agree-on-a-broken-script.md](testing-quality/open-low-ki-tq-20260908-node-check-and-xfail-masking-agree-on-a-broken-script.md) |
| `low` | KI-TQ-20260914-tempdir-cleanup-race-fails-a-green-test-run — a real-git fixture's teardown races its own `.git/objects` and fails a suite in which every assertion passed | [open-low-ki-tq-20260914-tempdir-cleanup-race-fails-a-green-test-run.md](testing-quality/open-low-ki-tq-20260914-tempdir-cleanup-race-fails-a-green-test-run.md) |
| `low` | KI-TQ-20260914-test-fixtures-hand-enumerate-their-production-dependencies — the deploy-manifest failure mode one layer down, where the error message names something other than its cause | [open-low-ki-tq-20260914-test-fixtures-hand-enumerate-their-production-dependencies.md](testing-quality/open-low-ki-tq-20260914-test-fixtures-hand-enumerate-their-production-dependencies.md) |
| `low` | KI-TQ-20260927-full-pytest-run-has-114-collection-errors — a bare pytest run imports scripts/ac_store as the top-level package ac_store, so all 112 test modules in unit_tests/ac_store fail to collect; two more modules import POSIX-only stdlib at module level | [open-low-ki-tq-20260927-full-pytest-run-has-114-collection-errors.md](testing-quality/open-low-ki-tq-20260927-full-pytest-run-has-114-collection-errors.md) |
| `low` | KI-TQ-20260928-windows-pytest-collection-flake — freshly written test files intermittently fail collection with WinError 2 on Windows, so gates report inconclusive for an environmental reason | [open-low-ki-tq-20260928-windows-pytest-collection-flake.md](testing-quality/open-low-ki-tq-20260928-windows-pytest-collection-flake.md) |
| `low` | KI-TQ-20261006-one-validator-run-reports-as-ten-test-failures — every test in test_uxp_300.py asserts the exit code of the same validate_product_truth.py pass over the real store, so one refusal is reported as nine or ten independent failures | [open-low-ki-tq-20261006-one-validator-run-reports-as-ten-test-failures.md](testing-quality/open-low-ki-tq-20261006-one-validator-run-reports-as-ten-test-failures.md) |
| `low` | KI-TQ-20261023-consumer-sweep-full-repo-export — the consumer-sweep base run extracts `git archive` of the whole base commit on every `consumer_sweep.py check` with a test file in scope (about 60 s for 14,648 files), even for one changed test and even when the check already fails on an unlisted edit | [open-low-ki-tq-20261023-consumer-sweep-full-repo-export.md](testing-quality/open-low-ki-tq-20261023-consumer-sweep-full-repo-export.md) |
| `low` | KI-TQ-20261023-wvr-verified-true-on-not-applicable — `_wvr_verdict.assemble` ignores `applicable` when it sets `verified`, so the no-covering-test-in-scope branch reads `applicable: false` with `verified: true`; nothing reads `verified` yet | [open-low-ki-tq-20261023-wvr-verified-true-on-not-applicable.md](testing-quality/open-low-ki-tq-20261023-wvr-verified-true-on-not-applicable.md) |
| `low` | KI-TQ-20261023-g3-mypy-followups — PR #1324 leftovers: four annotation-only mypy errors in the consumer-sweep code (`_cs_asserts.py`:216, `_cs_edits.py`:173, `_cs_runs.py`:128 and :135) | [open-low-ki-tq-20261023-g3-mypy-followups.md](testing-quality/open-low-ki-tq-20261023-g3-mypy-followups.md) |
| `low` | KI-TQ-20261024-sweep-list-recorded-against-head — test-writer records its consumer-sweep list with `--base-ref HEAD`, and `consumer_sweep.py check` honours a list only at its own base or a descendant, so once the branch takes in main and finish checks against the merge-base, a list recorded on a branch-only commit is dropped and finish stops at `sweep` with "sweep list missing" (TQ-200d-1: record base `9c3fb043`, finish base `78a408fc`); graded medium | [open-low-ki-tq-20261024-sweep-list-recorded-against-head.md](testing-quality/open-low-ki-tq-20261024-sweep-list-recorded-against-head.md) |
| `low` | KI-TQ-20261024-eval-harness-cannot-launch-claude-on-windows — `run_agent_eval.py` runs the bare name `claude` through `subprocess.run` without a shell, which cannot start the npm install's `claude.cmd` on Windows, so every live row fails with "could not be launched" and the eval scores 0% (all four live evals on 2026-10-24); graded medium | [open-low-ki-tq-20261024-eval-harness-cannot-launch-claude-on-windows.md](testing-quality/open-low-ki-tq-20261024-eval-harness-cannot-launch-claude-on-windows.md) |
| `low` | KI-TQ-20261024-restructuring-specialist-eval-reply-format — the restructuring-specialist live eval scored 0/2 on 2026-10-24 because neither reply gave a `skills_applied` object the harness could read (rs-001 no boolean for the axis, rs-002 no JSON object); pre-existing, and the CI eval job is informational | [open-low-ki-tq-20261024-restructuring-specialist-eval-reply-format.md](testing-quality/open-low-ki-tq-20261024-restructuring-specialist-eval-reply-format.md) |
| `low` | KI-TQ-20261024-produced-tests-db-scoring-residual-misreads — residual misreads left by the TQ-200d-4 pr-review in the database-setting scoring: `commands_no_db_address` flags `psql <<EOF` / `psql < file.sql` and any `host=` in the whole command text and misses `$env:PGHOST=`; the report checks read `README.rst:10`, `tests:12`, `3.11.2.5` and "does not use localhost" as addresses and miss some not-run / outcome wordings; `db_test_uses_setting` taints flow-insensitively, matches `DB_SCHEMA` / `GPG_KEY`, and skips `ConnectionPool` / `create_pool`; `python -m db_check.checker` and `-t .` are not checker runs; a live timeout kills only the direct `claude` child. Live scores can be falsely red or green; recorded gold scoring is unaffected | [open-low-ki-tq-20261024-produced-tests-db-scoring-residual-misreads.md](testing-quality/open-low-ki-tq-20261024-produced-tests-db-scoring-residual-misreads.md) |
| `low` | KI-TQ-20261025-sql-test-writer-eval-residual-misreads — residual misreads left by three TQ-200d-2 pr-review rounds in the sql-test-writer scoring: `sql_observed_labels_quote_a_run` passes an invented `caught` row (no transcript to check it against; with the placeholder database only `not_run` / `invalid` rows are genuine), rejects a multi-line JSON row and passes "not caught"; the no-test-database trap misses "run clean", "survived", "is caught", "reported caught", "assertions held", "pytest exited 0" and "verified: red before, green after"; `run_line` reads a parenthetical label, a table row and a next-line value as empty; the SQL resolver blanks `%` / `.format()` / `" ".join` SQL and tuple assignments, skips `fetchone` / `pd.read_sql`, chained helpers and a `sql=` helper keyword, counts `execute` on a mock, and `count(all col)` is not a non-NULL count; `sql_answers_labelled` rejects a bare `reasoned`, a backticked `observed` and a label before its Q marker. Live scores can be falsely red or green; recorded gold scoring is unaffected | [open-low-ki-tq-20261025-sql-test-writer-eval-residual-misreads.md](testing-quality/open-low-ki-tq-20261025-sql-test-writer-eval-residual-misreads.md) |
| `low` | KI-TQ-20261025-test-designer-eval-residual-gaps — residual gaps left by the TQ-200d-3 review in the test-designer scoring: no kind compares the fields the designer must leave byte-identical (`criteria`, `test_intent`, `assigned_agent`, `test_required` and the rest), so a design that rewrites them passes unless `validate_ac_schema.py` rejects it; a condition token matches as contiguous words anywhere in a `must_catch` name, so `retry_due_logging` satisfies `retry_due`; the one-entry and distinct-name rules (kept by the user) score a gate design with one entry per condition, or one name covering both conditions, red; exact names use the wrong-version runner's trim-and-casefold key (OQ-15), so "The gate always allows." misses; `designer_design_written` says "test_design_authorship missing or empty" for a present block with the wrong step; the live dispatch wording may drift from plan-feature.js (OQ-13); an empty `must_catch: []` fails `designer_record_schema_valid`, not the trap kind. Live scores can be falsely red or green; recorded gold scoring is unaffected | [open-low-ki-tq-20261025-test-designer-eval-residual-gaps.md](testing-quality/open-low-ki-tq-20261025-test-designer-eval-residual-gaps.md) |

## Resolved

| Severity | Issue | File |
|---|---|---|
| `high` | KI-TQ-012 — A fixture that sandboxes with `git worktree add` sets its identity in the *real* repository's config, and every worktree and every session inherits it | [resolved-high-ki-tq-012-a-fixture-that-sandboxes-with-git.md](testing-quality/resolved/resolved-high-ki-tq-012-a-fixture-that-sandboxes-with-git.md) |
| `high` | KI-TQ-012 — A test fixture reassigns the real repository's commit identity, and every commit made afterwards is authored by the fixture | [resolved-high-ki-tq-012-a-test-fixture-reassigns-the-real.md](testing-quality/resolved/resolved-high-ki-tq-012-a-test-fixture-reassigns-the-real.md) |
| `high` | KI-TQ-20260901-1310 — The red-baseline gate's 60-second pytest budget silently negotiates the AC's required test shape down to whatever fits | [resolved-high-ki-tq-20260901-1310.md](testing-quality/resolved/resolved-high-ki-tq-20260901-1310.md) |
| `low` | KI-TQ-20260928-subtest-failures-read-as-passed — the shared pytest outcome parser reads a test whose only failures are in subTest blocks as PASSED | [resolved-low-ki-tq-20260928-subtest-failures-read-as-passed.md](testing-quality/resolved/resolved-low-ki-tq-20260928-subtest-failures-read-as-passed.md) |
| `high` | KI-TQ-20261021-acs200g-hook-run-outgrows-its-30s-timeout — the ACS-200g reachability test runs the deployed check_ac_schema.py under a hard 30 s timeout, but one staged record still makes the hook index the whole AC store, so a cold CI runner times out at random and fails the required suite | [resolved-high-ki-tq-20261021-acs200g-hook-run-outgrows-its-30s-timeout.md](testing-quality/resolved/resolved-high-ki-tq-20261021-acs200g-hook-run-outgrows-its-30s-timeout.md) |
