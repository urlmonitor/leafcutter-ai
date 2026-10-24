---
title: "KI-TQ-20261023-g3-mypy-followups — four mypy errors in the consumer-sweep code (TQ-500g-3), all annotation-only"
description: "low — CI's informational mypy check on PR #1324 reports four errors in scripts/build_orchestration: _cs_asserts.py:216 passes list[ast.Call] where _by_position takes list[ast.AST] (list is invariant), _cs_edits.py:173 needs an annotation for `listed`, and _cs_runs.py:128 and :135 use Popen.stdout, typed IO[bytes] | None, without narrowing. No behaviour impact."
type: reference
category: reference
status: active
created: '2026-10-23'
last_updated: '2026-10-23'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
  - docs/known-issues/build-orchestration/open-low-ki-bo-20261023-g2-followups.md
---

# KI-TQ-20261023-g3-mypy-followups — four mypy errors in the consumer-sweep code

> Filed 2026-10-23. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** low. No behaviour is wrong. The mypy check is informational, and each error is a
  typing gap on a path that works at run time.
- **Status:** open, no AC.
- **Occurrences:** 1 (PR #1324's CI, run 39954931311, job "Type-check changed files (mypy,
  informational)", 2026-10-23).
- **First seen:** 2026-10-23 · **Last seen:** 2026-10-23
- **Where** (line numbers at `origin/main` `ae3a1591c`, mypy output reproduced locally with the
  CI flags `--ignore-missing-imports --explicit-package-bases`):

| File:line | mypy error | Cause |
|---|---|---|
| `scripts/build_orchestration/_cs_asserts.py`:216 | `Argument 1 to "_by_position" has incompatible type "list[Call]"; expected "list[AST]" [arg-type]` | `_approx_calls` (:213-216) passes a `list[ast.Call]` to `_by_position(nodes: list[ast.AST])` (:95). `list` is invariant. The line's `# type: ignore[return-value]` does not cover `arg-type`. |
| `scripts/build_orchestration/_cs_edits.py`:173 | `Need type annotation for "listed" [var-annotated]` | `listed = set()` in `unlisted_edits`. |
| `scripts/build_orchestration/_cs_runs.py`:128 | `Item "None" of "IO[bytes] \| None" has no attribute "read" [union-attr]` | `proc.stdout.read(...)` in `_export` (:121-140). `Popen.stdout` is typed optional; it is set because the call passes `stdout=subprocess.PIPE` (:125). |
| `scripts/build_orchestration/_cs_runs.py`:135 | `Item "None" of "IO[bytes] \| None" has no attribute "close" [union-attr]` | `proc.stdout.close()` in the same `finally`. |

All four came in with the TQ-500g-3 consumer-sweep work, merged by PR #1324 (`ae3a1591c`);
`_cs_asserts.py`:216 is from `0be96b86c` (TQ-500g-3-iii).

## Detection

From `scripts/build_orchestration/`:
`python -m mypy --ignore-missing-imports --explicit-package-bases --no-error-summary _cs_asserts.py _cs_edits.py _cs_runs.py`.

## Workaround

None needed. Read the mypy job as informational.

## Suggested fix

Directions only; nothing here is applied.

- `_cs_asserts.py`:95: type `_by_position` with a `TypeVar` bound to `ast.AST`
  (`def _by_position(nodes: Sequence[T]) -> list[T]`), and drop the `type: ignore` at :216.
- `_cs_edits.py`:173: annotate `listed: set[tuple[object, str, object]]`. The loop adds
  `(e.get("file"), name, e.get("fingerprint"))` tuples (:177), and the entries are plain dicts, so
  the first and third items are not known to be `str`.
- `_cs_runs.py`:125-135: bind `stdout = proc.stdout` after the `Popen` call and
  `assert stdout is not None` (it always is with `stdout=PIPE`), then use `stdout` at :127, :128
  and :135. Check the file-size ratchet before adding lines.

**Related.** `KI-BO-20261023-g2-followups` records the same kind of leftovers from PR #1316.
