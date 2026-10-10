---
title: "KI-CG-20260909-gate-folder-density — `check-folder-density`'s grandfather compares `git ls-files`, which already includes staged additions, so its blocking branch is unreachable"
description: "low — safe to register, but it is not an enforcing gate and would print a warning block on most commits."
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-10-10'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
  - docs/known-issues/commit-guardian/open-high-ki-cg-20261010-folder-density-refuses-merges-of-main.md
---

# KI-CG-20260909-gate-folder-density — `check-folder-density`'s grandfather compares `git ls-files`, which already includes staged additions, so its blocking branch is unreachable

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** low — safe to register, but it is not an enforcing gate and would print a warning block on most commits.
- **Status:** open — no AC.
- **Occurrences:** measured once, `df1f0cfb5`. · **First seen:** 2026-09-09 · **Last seen:** 2026-09-09
- **Where:** `templates/scripts/commit_guardian/check_folder_density.py`; limit 15 non-`.md`, non-`__init__.py` files per directory.

**The mechanism.** It computes `before_counts` from `git ls-files` to decide whether a directory was already over the limit. But `git ls-files` lists staged-but-uncommitted additions, so in a real pre-commit run `before == after` — every over-limit directory takes the `before > limit → warning` branch and the blocking branch is never reached. The grandfather is not too lenient by design; it is accidentally total.

**The numbers.** 107 of 261 directories are over 15, up to 174 files in `docs/acceptance-criteria/ac-driven-dev`. Registering as-is prints a "PRE-EXISTING DENSITY" block naming them on most commits.

**Fix.** Take `before_counts` from `HEAD` (`git ls-tree`), not `git ls-files`. That makes the existing grandfather work as intended: the 107 stay tolerated, and adding a 16th file to a compliant directory is refused. This is a genuine ratchet already written — it just reads the wrong source.

**Definition of done.** `before_counts` reads `HEAD`; the 107 stay green; adding a file that takes a compliant directory over 15 is refused; noise is bounded.

---

**Update, 2026-10-10.** The fix above appears to have landed: `d8cd00a9d` (GE-120h-3, on main
through PR #1067, 2026-10-09) reads BEFORE with `git ls-tree -r HEAD`
(`check_folder_density.py:124-170` on `d03830e7c`). This entry was not moved to `resolved/` here;
check the definition of done before moving it. Reading HEAD alone exposed a different defect in
merge commits: `KI-CG-20261010-folder-density-refuses-merges-of-main`.
