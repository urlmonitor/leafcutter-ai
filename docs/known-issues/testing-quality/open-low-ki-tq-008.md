---
title: "KI-TQ-008 — A repository-global tree-purity guard false-positives under concurrent agents"
description: "medium — it manufactures failures indistinguishable from real ones"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
---

# KI-TQ-008 — A repository-global tree-purity guard false-positives under concurrent agents

> One known issue, split out of `docs/known-issues/testing-quality.md` on
> 2026-09-14. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium — it manufactures failures indistinguishable from real ones
- **Status:** open — **the test file is NOT on `main`**; it lives on unmerged PR #495. Filed
  because the guard is good practice and will be copied, and the scoping defect should be fixed
  before it is.
- **Occurrences:** 3 (one session)
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-19
- **Where:** PR #495's `test_ge_122e_3.py` — `tearDownModule`

**Symptom.** The module has a `tearDownModule` that proves it never wrote to the real repository
— it snapshots `git status --porcelain` before the module runs and compares afterwards. The
guard itself is good practice: every fixture operates on a `shutil.copytree`'d tempdir, and this
catches a bug in the test file's own fixture code escaping the tempdir.

The problem is that `git status --porcelain` is **repository-global**. The guard cannot
distinguish "this module escaped its tempdir" from "some other process touched the tree", so
**any** concurrent activity trips it:

```
RuntimeError: The real repository working tree changed during this test
module's run.
BEFORE: ... (12 modified files)
AFTER:  ... + tickets/.../03_TICKET-20260818-GE-122a-2.md
```

That diff is a *different* agent editing a *different* ticket. Nothing was wrong.

**Evidence.** Observed three times in one session while several agents worked in one worktree.
Each occurrence cost an agent a diagnostic detour and a re-run. Two agents correctly identified
it as spurious; the danger is the third that does not — the failure is loud, alarming, and points
at the wrong thing. The mirror-image risk is an agent learning to dismiss this error and thereby
missing a real escape.

**Detection.** Compare the BEFORE and AFTER strings in the error. If the only difference is a
file this test module has no business touching, it is interference.

**Workaround.** Do not run the suite while another agent is writing to the worktree, and do not
write to the worktree while a suite is running. One writer at a time.

**Fix direction.** Narrow the guard's scope: snapshot only the paths this module could plausibly
touch (`docs/acceptance-criteria/`, `docs/architecture/`, `tickets/`), or diff only against paths
under `_REPO_ROOT` that the module's own fixtures reference. **Keep the guard** — it is the right
idea, just too wide.

---
