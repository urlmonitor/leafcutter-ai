---
title: "KI-BO-20261023-g2-followups — leftovers from PR #1316 (TQ-500g-2): three mypy errors in new code, and sql-test-writer still declares itself read-only although it writes files"
description: "low — CI's informational mypy check reports three errors in code added by PR #1316: wrong_version_runner.py:274 unpacks ctx.db_seen, which is typed Optional; _tq500g2i_standin_pg.py:90 assigns FrameType | None to a FrameType variable; _tq500g2i_review_fixtures.py:76 divides a Path | None. Separately, templates/agents/sql-test-writer.md's frontmatter says mutates: none ('Read-only agent') while the agent writes test files and, since #1316, <git-dir>/leafcutter/to-run-later/<ac-id>.json."
type: reference
category: reference
status: active
created: '2026-10-23'
last_updated: '2026-10-23'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-20261023-g2-followups — small leftovers from PR #1316

> Filed 2026-10-23. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** low. No behaviour is wrong today. The mypy check is informational and none of the
  three errors is reached at run time on the paths that exist. The frontmatter error misleads a
  reader or tool that trusts `mutates`.
- **Status:** open, no AC.
- **Occurrences:** 1 (found in PR #1316's CI and review, 2026-10-22).
- **First seen:** 2026-10-22 · **Last seen:** 2026-10-23
- **Where** (line numbers at `origin/main` `212a126bf`, mypy output reproduced locally with the
  CI flags `--ignore-missing-imports --explicit-package-bases`):

### (a) mypy errors in new code

| File:line | mypy error | Cause |
|---|---|---|
| `scripts/build_orchestration/wrong_version_runner.py`:274 | `Expected iterable as variadic argument [misc]` | `db_mod.judge(new, *ctx.db_seen, ...)`. `db_seen` is declared `tuple[db_mod.Session, dict] \| None = None` (:122) and set at :235. |
| `unit_tests/build_orchestration/_tq500g2i_standin_pg.py`:90 | `Incompatible types in assignment (expression has type "FrameType \| None", variable has type "FrameType") [assignment]` | `frame = frame.f_back` in `_from_plugin`; `frame` is first set from `sys._getframe(1)` (:86). |
| `unit_tests/build_orchestration/_tq500g2i_review_fixtures.py`:76 | `Unsupported left operand type for / ("None") [operator]` | `block / f"{module}.py"`; `block` is `root / "block" if blocked else None` (:74). The loop only runs when `blocked` is non-empty, which mypy cannot see. |

All three came in with PR #1316 (`07795ffa8`, TQ-500g-2-i, and the TQ-500g-2-i review fixtures).

### (b) sql-test-writer declares itself read-only

`templates/agents/sql-test-writer.md`:29-32 has `mutates: none` with the description "Read-only
agent — no filesystem mutations". The same file gives the agent `Write` and `Edit` (:10), and its
body has it write test files and, since PR #1316 (`7645987ce`, TQ-500g-2), the hand-on file
`<git-dir>/leafcutter/to-run-later/<ac-id>.json` (:320-324). The read-only line dates from the
self-description metadata pass (`1c27d8b0e`, #65), so it was wrong before #1316; #1316 widened
the gap.

## Detection

- (a) `python -m mypy --ignore-missing-imports --explicit-package-bases --no-error-summary` on the
  three files.
- (b) Compare the `mutates:` block with the agent's `tools:` line and its write steps.

## Workaround

None needed. Read the mypy job as informational, and do not trust `mutates` for this agent.

## Suggested fix

Directions only; nothing here is applied.

- `wrong_version_runner.py`:274: guard `ctx.db_seen` before unpacking. It is set by `_db_put_back`
  (:235) inside `_apply_run_restore`, which runs just before :274, so an
  `assert ctx.db_seen is not None` or a narrowed local states what the code already relies on. Check
  the file-size ratchet before adding lines.
- `_tq500g2i_standin_pg.py`:86: annotate `frame: FrameType | None`.
- `_tq500g2i_review_fixtures.py`:74-76: narrow `block` inside the loop, or build it only when
  `blocked` is non-empty and type it `Path`.
- `sql-test-writer.md`:29-32: list the real mutations (the test files it writes, and the
  to-run-later file under the git dir), and check the description line "writes no auxiliary
  output inside the project tree" still holds.
