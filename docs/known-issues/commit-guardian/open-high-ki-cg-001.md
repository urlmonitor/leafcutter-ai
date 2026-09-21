---
title: "KI-CG-001 — AC hooks are scoped to the git index, so parent-level drift is unreachable"
description: "KI-CG-001 — AC hooks are scoped to the git index, so parent-level drift is unreachable"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-001 — AC hooks are scoped to the git index, so parent-level drift is unreachable

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 2
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-19
- **Where:** `templates/scripts/commit_guardian/check_ac_parent_covered_by.py:134-150`, and the AC hook family generally

**Second occurrence, 2026-08-19.** Staging `GE-113c-1-iii` and `GE-113c-1-v` for an
unrelated one-line `components` edit made `check-ac-schema` fail both with *"approved code
AC must declare a test contract — add a non-empty `test_spec`"*. Neither record has ever
had one. They are `readiness: approved`, `change_target: code`, and have been sitting on
`main` in that state — invisible because no commit had happened to stage them since the
rule was introduced. The hook was not silent because they were fine; it was silent because
it had never been shown them. A store-wide sweep would find how many more there are; the
index-scoped hook structurally cannot.

**Symptom.** These hooks derive their file list from `git diff --cached --name-only` (or
`HOOK_TEST_FILES` under test) — never from the store. Any fact that is true of the store
but not of the staged set is structurally invisible. Because normal work edits children
and leaves the parent untouched, the parent is almost never staged, so the hooks that
exist to check parents are almost never handed one. Their silence reads as a pass; it
means they were not given the file.

**Evidence.** `ACD-400a` on `main` at `439b9076f` carries **both** failure modes at once:
`covered_by: [ACD-400a-1, ACD-400a-2]` while `ACD-400a-3` and `-4` have existed on disk
since 2026-08-12, and `work_status: done` while `ACD-400a-1` and `-2` are both still
`todo`. Every commit in that five-day window passed every AC hook. It surfaced only when
the parent was incidentally staged on 2026-08-18.

It is not an isolated record. A read-only sweep of all 3,146 store records at the same
commit found **20** composites marked `done` with at least one unfinished child —
`ACD-300a`, `ACD-400b` and `ACD-600a` each with 3-4 `todo` children. Sixteen are L2; in
thirteen of those, every unfinished child is a Roman-suffixed technical-constraint
sibling, so the dominant shape is flipping an L2 to `done` once its behaviour works while
its `-i` constraints stay `todo`.

Two aggravating details. These hooks fail open on unexpected exceptions, so an error is
also silent. And they ignore `argv`: passing a path on the command line does not make
them check that path, which makes them easy to "verify" without having verified anything.

**Fix direction.** For any staged AC, resolve and check its parent from the store whether
or not the parent is staged — the store is on disk and cheap to read. A store-wide sweep
in CI would also catch existing drift, which per-commit hooks by construction never will.
Until then, the workaround is documented in `CLAUDE.md` → "AC-store commits — stage the
parent alongside the child".

**Pattern:** `docs/reference/false-green-mechanisms.md` → M3.

---
