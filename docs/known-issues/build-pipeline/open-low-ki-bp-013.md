---
title: "KI-BP-013 — The mypy gate checks only changed files, so untouched debt is invisible until an unrelated edit drops a wall of it on whoever touched the file"
description: "KI-BP-013 — The mypy gate checks only changed files, so untouched debt is invisible until an unrelated edit drops a wall of it on whoever touched the file"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_pipeline
related_docs:
  - docs/known-issues/build-pipeline.md
  - docs/known-issues/README.md
---

# KI-BP-013 — The mypy gate checks only changed files, so untouched debt is invisible until an unrelated edit drops a wall of it on whoever touched the file

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../build-pipeline.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** low
- **Status:** open — the gate is informational, so this costs attention rather than merges
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** the `Type-check changed files (mypy, informational)` job in `.github/workflows/ci.yml`

**Symptom.** The job type-checks the files a PR changed. A file that has never been changed
since the job was introduced has never been checked, however much it violates. The first commit
to touch it — for any reason, of any size — inherits every accumulated error as a red check on
its own PR.

**Evidence.** PR #541 changed **two lines** in
`unit_tests/build_orchestration/test_bo2400f_lifecycle.py`: a `chmod` widened from a file to its
containing directory, plus the matching restore in `finally`. The mypy job went red with **22
errors**, all `"None" not callable`, at lines scattered from 324 to 1366 — nowhere near the
edit.

Confirmed pre-existing rather than introduced, by running mypy against `origin/main`'s
unmodified copy of the same file:

```
$ git show origin/main:unit_tests/build_orchestration/test_bo2400f_lifecycle.py > /tmp/main_copy.py
$ mypy /tmp/main_copy.py --ignore-missing-imports
Found 22 errors in 1 file (checked 1 source file)
```

Same 22. Meanwhile mypy is green on `main` itself, because `main` never changes that file.

**Why it matters more than the severity suggests.** The signal is anti-correlated with
responsibility: the person who least touched the file gets the whole report. The rational
response is to shrug, and shrugging at a red check is a habit worth not building — especially on
a job that would otherwise be a useful early warning. It also makes the gate useless as a ratchet:
debt cannot decrease, because nothing ever forces a file to be looked at.

**Related shape.** `KI-CG-015` and `KI-CG-012` describe the same "invisible until touched"
property in the AC-schema hooks, where the consequence is worse because those gates are blocking.
This is the same design choice with a softer landing.

**Fix directions.** Either run mypy over the whole tree with a baseline file (so existing errors
are recorded and only *new* ones fail — the standard ratchet), or keep changed-files scoping but
report pre-existing errors separately from ones the PR introduced, so the diff-attributable count
is visible at a glance. The second is cheaper and preserves the current signal; the first
actually retires the debt.

---
