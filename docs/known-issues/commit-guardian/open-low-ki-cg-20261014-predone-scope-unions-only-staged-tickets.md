---
title: "KI-CG-20261014-predone-scope-unions-only-staged-tickets — check-predone-scope compares the whole branch diff with only the done tickets staged in this commit, so every later group of a multi-commit epic branch is refused"
description: "medium — check_files_touched_reconciliation unions the files_touched of the done tickets STAGED in the current commit but compares them with the branch diff against origin/main plus the staged files. On an epic branch built group by group, the second group's commit is refused for files the first group's already-committed, already-done tickets declare, so the only ways through are false files_touched entries or a user-authorized SKIP=check-predone-scope."
type: reference
category: reference
status: active
created: '2026-10-14'
last_updated: '2026-10-14'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-20261014-predone-scope-unions-only-staged-tickets — check-predone-scope unions only the staged done tickets

> Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below.

- **Severity:** medium. Nothing wrong lands. But every commit after the first on a multi-commit
  epic branch is refused, so the choice is false `files_touched` entries or a user-authorized
  `SKIP=check-predone-scope`. That skip also hides real undeclared changes for the rest of the epic.
- **Status:** open, no AC.
- **Occurrences:** 1 (EPIC-RightJobRightAgent, G2 commit `e5ecfdbf7`, 2026-10-14). The user
  authorized skipping this hook for the rest of that epic. · **First seen:** 2026-10-14 ·
  **Last seen:** 2026-10-14
- **Where:** `templates/scripts/commit_guardian/hooks/check_files_touched_reconciliation.py`
  (deployed as `scripts/commit_guardian/hooks/check_files_touched_reconciliation.py`), `main()`
  pass 1 and pass 2, and `_get_branch_diff_files()`.

## The mismatch

1. **The changed set is branch-wide.** `_get_branch_diff_files()` returns every file changed on
   the branch against `origin/main` (or `main`). `_compute_undeclared()` adds the staged files.
2. **The declared set is commit-local.** Pass 1 unions the `files_touched` and `out_of_scope` of
   the done tickets staged in this commit only.
3. **The two sets have different scopes.** Take a branch whose first commit closes tickets A and
   whose second commit closes tickets B. In the second commit, A's files are in the changed set,
   but A's tickets are not staged, so their scopes are missing from the union. B is then told to
   declare files it never touched.

## Seen

On EPIC-RightJobRightAgent, the G1 tickets were closed and committed in `e470dbf98`. The G2 commit
closed tickets 07–19 and declared every file G2 changed, and was still refused for 21 G1 files.
Examples are `scripts/ac_store/_impl_readiness_gate.py`, `scripts/ac_store/scan_ac_store.py`,
`scripts/build.py` and `tests/ac_store/test_tkt_600a_3.py`. It was committed with
`SKIP=check-predone-scope` under the user's authorization, stated in the commit message.

## Fix direction

The two sides must have the same scope. Any one of these closes it:

- **Union every done ticket on the branch.** Use every ticket that is `status: done` at the
  staged tree and whose file changed on the branch. This keeps the branch-wide changed set.
- **Narrow the changed set.** Use only the staged files plus the files of commits that touch
  the staged tickets. This keeps the commit-local declared set.
