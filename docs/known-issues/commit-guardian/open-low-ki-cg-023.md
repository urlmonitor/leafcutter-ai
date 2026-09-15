---
title: "KI-CG-023 — `check-predone-scope` cannot distinguish a ticket's subject from its driver, and reconciles branch-wide rather than commit-wide"
description: "KI-CG-023 — `check-predone-scope` cannot distinguish a ticket's subject from its driver, and reconciles branch-wide rather than commit-wide"
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

# KI-CG-023 — `check-predone-scope` cannot distinguish a ticket's subject from its driver, and reconciles branch-wide rather than commit-wide

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open — code is on `main` and live, but **advisory by default**
  (`files_touched_reconciliation.strict: false`), which is what keeps this at medium rather
  than the blocker severity observed on the branch, where it was hit in strict mode
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-26 (re-verified against `37655862`)
- **Where:** `templates/scripts/commit_guardian/hooks/check_files_touched_reconciliation.py`
  — `_reconcile` (`all_changed = branch_diff_files | frozenset(staged_files)`, ~:451) and
  `_get_branch_diff_files` (:113-132); registered as `check-predone-scope` in
  `commit_guardian.json:589`

**Symptom.** The hook reads every modified ticket `.md` in the change set as a *governing*
ticket authorising the commit, then reports source changes as undeclared against that
ticket's `files_touched`. It has no notion of a ticket being the *subject* of a change.

This misfires on any work that repairs tickets. GE-122e-2 deleted five duplicate work items;
the hook read those five long-finished June tickets as the commit's authorisers and blocked.

**Second, compounding defect: it reconciles branch-wide, not commit-wide.** An attempt to
satisfy it by splitting the source changes into a separate commit still failed, and the error
named files that were not in the commit at all (`_commit_disposition.py`,
`_uniqueness_scanners.py`, `_work_items_scanner.py` — all from earlier commits on the
branch). No commit boundary can satisfy it.

**Evidence.** Both defects are visible in the hook's own source on `main`. Its module
docstring states it *"Computes branch diff plus staged source files"* and that *"when
multiple done tickets are staged together, reconciliation uses the UNION"* — the two
behaviours described above, documented as intent. The union is computed at
`all_changed = branch_diff_files | frozenset(staged_files)`.

**Detection.** The tell is a blocker (or advisory) naming files absent from
`git diff --staged`.

**Fix direction.** Two independent changes: (1) distinguish subject from driver, probably by
treating a ticket as governing only when the commit is authored under it; (2) reconcile
against the staged diff rather than the branch diff. Until then, `SKIP=check-predone-scope`
with the justification written into the commit message — used once on `6715e4c3`.

**Pattern:** a scope check whose population is the branch while its subject is the commit.
The same population-vs-change mismatch as `KI-CG-001`.

---
