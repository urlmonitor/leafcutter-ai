---
title: "KI-CG-009 — `check-components-integrity` resolves the repo root to the main checkout instead of the worktree, so a branch-only `detail_ref` doc is reported missing"
description: "KI-CG-009 — `check-components-integrity` resolves the repo root to the main checkout instead of the worktree, so a branch-only `detail_ref` doc is reported missing"
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

# KI-CG-009 — `check-components-integrity` resolves the repo root to the main checkout instead of the worktree, so a branch-only `detail_ref` doc is reported missing

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `templates/scripts/commit_guardian/check_components_integrity.py` — `_repo_root()` (`:134-175`), the module-level `REPO_ROOT` binding (`:127`), and the `detail_ref` existence check `doc_path = root / detail_ref` (`:657`)
- **Reported by:** customer bug report, 2026-08-25

**Symptom.** Committing in a git worktree, the hook reports a component's `detail_ref`
architecture doc as missing even though the doc exists on the branch being committed. The
file is there and is reachable; the hook is reading a *different*, perfectly valid checkout
and truthfully reporting that the doc is not in that tree. The failure message does not name
the root it used, so it reads as "you forgot to write the doc" while the doc sits in front of
you.

**Root cause.** `_repo_root()` — added by `ACS-300g-6` — resolves the root by running
`git rev-parse --show-toplevel`, which is CWD-based and therefore correct inside a worktree.
Its fallback is not. The fallback is `Path(__file__).resolve().parents[2]`, and in a worktree
`.leafcutter` is commonly a **symlink** to the workspace parent's `.leafcutter` — the layout
this package's own `CLAUDE.md` → "Worktree pre-commit config" explicitly recommends.
`Path.resolve()` follows that symlink before `parents[2]` is taken, so the fallback lands on
the **main workspace checkout** rather than on the worktree being committed to. The one
resolution path meant to be the safety net is the path that walks out of the repository you
are committing to.

There is a second, independent half. The module-level `REPO_ROOT` (`:127`) is bound to that
same `__file__`-relative expression **at import time** and is only corrected inside `main()`.
Any code path reading `REPO_ROOT` before or outside `main()` therefore gets the wrong root no
matter what `_repo_root()` would have returned — `validate_component_entry`'s own
`doc_path = REPO_ROOT / detail_ref` (`:433`) is exactly such a consumer. Repairing only the
fallback expression leaves this half live.

**Why it matters.** The file exists, on the branch being committed; the hook simply computes
the wrong root. The symlinked `.leafcutter` layout is not an exotic setup someone talked
themselves into — it is the documented, supported one, so a hook that breaks under it is the
thing that is wrong, not the layout. The practical workaround is `SKIP=`, which is precisely
the reflex this repo is trying to eliminate: a guard that must be bypassed to commit correct
work teaches people to bypass guards. There is a false-green corollary too — a `detail_ref`
that exists in the main checkout but *not* on the branch being committed passes this gate for
the same reason, landing a registry entry that points at a doc the branch does not contain.

**Evidence.** Reported by a customer on 2026-08-25, committing from a worktree whose
`.leafcutter` was a symlink to the workspace parent's. The code facts are directly readable:
`REPO_ROOT: Path = Path(__file__).resolve().parents[2]` at `:127`, under a comment stating
*"main() updates this via _repo_root()"*, and `_repo_root()`'s two fallback branches at
`:161-174`, both returning `_fallback = Path(__file__).resolve().parents[2]`. The helper's
docstring claim that it is *"correct regardless of where the hook file lives (e.g. via a
.leafcutter symlink into another repo)"* holds only for the `git rev-parse` branch, not for
the fallback sitting immediately beneath it.

**AC coverage — already claimed, and already once phantom-done.** `ACS-300g-6` ("Component
integrity hook resolves REPO_ROOT to the actual repository top-level") names this invocation
path in its criteria verbatim: *"invoked through the `.leafcutter` symlink install path (so
that `Path(__file__).resolve().parents[2]` resolves to `<repo>/.leafcutter` rather than the
real repository root)"*. It was marked `work_status: done` on 2026-07-08 (commit `4216ddcf`)
and stayed that way for six weeks; it was reopened to `todo` on 2026-08-18 because the shipped
fix swapped a `__file__`-anchored root bug for a CWD-anchored one, and because its test never
exercised a symlinked `.leafcutter` or a linked worktree at all. So this is **incomplete
coverage on an AC that was already marked done** — a phantom-done instance with a paper trail,
not virgin territory, and the current customer report is that same defect resurfacing from a
second direction. Anyone picking this up should read that record's `notes` before writing a
line of code. Store anomaly worth recording alongside it: `ACS-300g-6` carries
`covered_by: []` while its `implemented_by` names a test file — the coverage link that would
have exposed the gap was never made.

**Fix direction.** Never resolve the root through the `.leafcutter` symlink. Prefer the
`git rev-parse --show-toplevel` result and, when it fails, derive the root from the **CWD**
rather than from `__file__` — the question being asked is "which tree is being committed to",
and `__file__` cannot answer that once the hook is reached through a link. Bind `REPO_ROOT`
lazily, or thread the resolved root into every consumer the way `validate_new_component`
already does, so no caller can read the import-time fallback. Heed the trap recorded on
`ACS-300g-6`: the obvious regression test cannot fail, because a test run with the CWD already
at the worktree top-level returns the right root against broken and fixed code alike. A test
for this must exercise a symlinked `.leafcutter` **and** place the CWD somewhere other than
the worktree top-level, or it will be green against the defect — which is how this survived
the first time.

**Relationship to KI-BP-003.** Same symlinked-worktree setup, different defect, and the
distinction decides the fix. `KI-BP-003` is a **missing-artifact** failure: `config/doc_types.json`
was never deployed into the layout the hook runs in, so no amount of correct root resolution
would have found it and the repair belongs in the deploy manifest. This is a **wrong-tree**
failure: the file exists, on the branch being committed, and the hook reads a different
checkout — deploying more files fixes nothing here.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M2, the same family — a hook that
cannot reach a file it depends on because it is wrong about where it is — though M2's
mechanism is the deploy manifest and this one's is root resolution through a symlink.

---
