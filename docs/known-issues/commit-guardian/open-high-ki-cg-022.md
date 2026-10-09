---
title: "KI-CG-022 — `check_adr_collision.py` exists but is registered nowhere, and the branch that registers it also makes it fail closed without `origin/main`"
description: "medium — **downgraded from the high recorded on the branch, because the"
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

# KI-CG-022 — `check_adr_collision.py` exists but is registered nowhere, and the branch that registers it also makes it fail closed without `origin/main`

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium — **downgraded from the high recorded on the branch, because the
  claim it rested on is false for `main`** (see Evidence)
- **Status:** open — the *script* is on `main` and has been since the initial commit; the
  *registration* and the *fail-closed behaviour* are **not** on `main` and live only on
  unmerged PR #495. The defect is therefore latent on `main` and becomes live the moment
  that branch lands.
- **Occurrences:** 2
- **First seen:** 2026-08-25 · **Last seen:** 2026-10-09 (still unregistered on `main`; see the 2026-10-09 note below)
- **Where:** `templates/scripts/commit_guardian/check_adr_collision.py:81-101`
  (`get_committed_adr_numbers`); `templates/scripts/commit_guardian/commit_guardian.json`

**Symptom (as observed on the branch).** The hook reads the decision-number sequence from
`origin/main` and fails closed when that ref does not exist:

```
[check_adr_collision] BLOCKED -- could not read the decision-number sequence:
  could not read the decision sequence on 'origin/main' (git ls-tree exited 128):
  fatal: Not a valid object name origin/main
[check_adr_collision] Uniqueness was not established, so this commit cannot proceed.
```

A `git init` repository has no `origin/main`. Every ADR-touching commit in any repo that is
not a clone with a `main` branch is blocked. Found while building a fresh consumer install
to test `KI-CG-021`.

**Evidence — the branch entry's own framing was wrong, and this is the correction.** The
branch recorded this as *"This hook IS registered and required … live on `main` today — not
introduced by this epic."* Both halves are false for `main`, verified directly at
`37655862`:

- **Not registered.** `grep -n 'check_adr_collision\|check-decision-number-uniqueness'
  templates/scripts/commit_guardian/commit_guardian.json` returns **nothing**, across all 55
  registered hooks. A repo-wide grep over `.json` / `.yaml` / `.yml` / `.py` / `.js` /
  `.toml` finds the name only in the script itself, `config/package_boundary.json`,
  `scripts/adr_refs.py`, and seven GE-12x AC records. No `.pre-commit-config.yaml` entry
  either. `git log -- templates/scripts/commit_guardian/check_adr_collision.py` shows the
  file present since `11dbd26b` (initial commit) and never registered since.
- **Not fail-closed.** `main`'s copy fails **open**. Its docstring states
  *"Empty on any error"* and the body is literally `if rc != 0: return set()`
  (`check_adr_collision.py:93-94`). The `BLOCKED -- could not read the decision-number
  sequence` string appears **nowhere** in the repository.

So the branch registered the hook (as `check-decision-number-uniqueness`) *and* converted it
from fail-open to fail-closed, then observed the consequence and recorded it as pre-existing.
It was neither.

**Why this matters more, not less.** `main` today has the opposite defect: a decision-number
collision detector that has never run in the package's entire history, silently returning an
empty set on any git error even where it *is* invoked by hand. And the branch's two changes
compose into the fresh-install blocker above. Landing PR #495 without addressing this ships
that blocker.

**Fix direction.** Treat as one change with three parts: register the hook; keep it fail-closed
(fail-open is what let it hide for months); and make an absent `origin/main` a *distinguishable*
condition — resolve the first ref that exists from `origin/main`, `main`, `HEAD` and only block
when none resolves, matching the `_resolve_first_ref` pattern
`unit_tests/commit_guardian/test_ge_122e_1.py:504` already uses for exactly this reason.

**Pattern:** an entry that mis-states which tree its evidence came from. Verification run on a
branch, recorded as a property of `main`.

**Second occurrence (2026-10-09), found while authoring ADR-068.** Still unregistered:
`grep -c check-adr-collision templates/scripts/commit_guardian/commit_guardian.json` returns
**0** on `main`, so number-collision protection remains manual-only. This matters more than
it did in August, because the procedure that stands in for the gate is itself unreliable from
the wrong directory:

- `docs/conventions/adr-numbering.md` §3 Step 2 prescribes running this hook as the
  pre-flight. Invoked with a cwd outside the git work tree — which is where this workspace's
  agent sessions start, the untracked workspace parent — it prints
  `BLOCKED -- could not read the decision-number sequence: could not list staged files
  (git diff exited 129): error: unknown option 'cached'`. Reproduced both ways on 2026-10-09:
  from the workspace parent it BLOCKS, from the repo root it is silent and clean. The cause is
  `_fetch_staged_adrs`'s `_run_git("diff", "--cached", ...)` at
  `templates/scripts/commit_guardian/check_adr_collision.py:139-141`, which never passes the
  `cwd` argument `_run_git` already accepts, so git inherits the process cwd and falls into
  `--no-index` mode. A BLOCKED verdict that means "I could not look" is the exact shape
  `CLAUDE.md`'s "before acting on a guard tool's FAILURE" rule exists for.
- `docs/conventions/adr-numbering.md` §6 and `write-adr.md` §10 make `scripts/adr_refs.py`'s
  unclaimed-number audit the required way to pick a number. Its `--root` defaults to **cwd**,
  so from the workspace parent it walks ~100 sibling worktrees: it produced no output in over
  five minutes and was reported as hung. It is not hung — with
  `--root <repo>` it completes in **5.0s**. Same cwd-default family as
  `KI-KM-20261008-harvest-state-default-is-cwd-relative`.

So all three legs of the documented numbering defence (the gate, its pre-flight, and the
audit) are currently either absent or silently wrong from the directory sessions actually run
in. ADR-068 was numbered by four independent manual checks instead — directory listing,
`git log --all --diff-filter=AR`, the `origin/main` tree, and a repo-wide citation grep.

---
