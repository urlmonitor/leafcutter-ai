---
title: "KI-BO-20261025-workspace-maker-clone-head-stale — two fresh workspaces answered status ok with base_commit at the current origin/main, but HEAD stood on an older origin/main with the newer tree staged; the reflog matches the stale in-repo copy of the maker, which still has the by-name checkout race fixed on main"
description: "medium — on 2026-10-25 `worktree.py ensure` made fastlane/tq-200d-3 and scratch/tq-200d-before-score, answered `status ok` with base_commit = the then-current origin/main, and left HEAD at 1a5c47cc3 (an older origin/main) with the newer main tree already in the index. In the scratch workspace (base 5e5a37380) git log -1 showed 1a5c47cc3 while git diff --cached 5e5a37380 was empty; in the fastlane one a later git merge left about 350 staged files and no MERGE_HEAD. The scratch workspace's reflog shows the branch 'Created from origin/main' with an upstream, after a fetch that rewound origin/main from 5e5a37380 to 1a5c47cc3 — the race fixed by 1d316e0a0 (PR #1351). The maker that ran was most likely the gitignored in-repo install leafcutter-ai/.leafcutter/scripts/worktree.py, deployed 2026-10-24 from 1a5c47cc3, before that fix; nothing in the answer shows which copy or build of the maker answered."
type: reference
category: reference
status: active
created: '2026-10-25'
last_updated: '2026-10-25'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
  - docs/how-to/get-a-workspace.md
---

# KI-BO-20261025-workspace-maker-clone-head-stale — a fresh workspace's HEAD is an older main than its files

> Filed 2026-10-25. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** medium. The answer is `status ok` with a correct-looking `base_commit`, so nothing
  warns the caller. The first commit or merge in such a workspace carries the whole gap between
  the two mains as staged changes (about 350 files in the fastlane case), which can reach a PR
  as unrelated diff or make a merge look broken. Each occurrence was caught by hand and repaired
  with a reset.
- **Status:** open, no AC.
- **Occurrences:** 2, both on 2026-10-25 on Windows 11, both fresh workspaces (`created`):
  - `fastlane/tq-200d-3`: HEAD at `1a5c47cc3`, the newer main tree staged. A later `git merge`
    left about 350 staged files and no `MERGE_HEAD`. Repaired by a reset and a re-fetch. The
    workspace is gone, so its reflog could not be read for this entry.
  - `scratch/tq-200d-before-score` (`leafcutter-ai-worktrees/scratch/tq-200d-before-score`):
    the answer's `base_commit` was `5e5a37380`; `git log -1` showed `1a5c47cc3` while
    `git diff --cached 5e5a37380` was empty. Repaired with `git reset --soft 5e5a37380`.
- **First seen:** 2026-10-25 · **Last seen:** 2026-10-25
- **Where** (line numbers at `origin/main` `5e5a37380` unless named otherwise):
  - **Likely site, the stale in-repo install:** `leafcutter-ai/.leafcutter/scripts/worktree.py`
    (gitignored, deployed 2026-10-24 19:14 UTC, the time `1a5c47cc3` merged). Its `_start_line`
    builds a new line with `["checkout", "-B", branch, "origin/main"]` (:86), resolving the start
    point by name, after `_checkout_line` has already read `origin/main` into `base_commit`
    (:107). It then runs the work set-aside around readiness for a created workspace too
    (:142). That is the pre-fix behaviour.
  - **The fix on main:** `1d316e0a0` "fix(worktree): a new workspace's line of work starts
    exactly where its files are, or the maker refuses" (ticket 11 of
    EPIC-WorkspaceMakerHardening, PR #1351). `templates/scripts/worktree_ensure_steps.py`:220-242,
    `build_line`, resolves one SHA, runs `checkout --no-track -B <branch> <sha>` (:238), and
    `_verify_built` (:200-206) refuses `VERIFY_FAILED` unless HEAD is that SHA on a clean tree;
    `templates/scripts/worktree.py`:126 skips the set-aside for a created workspace. The
    workspace-parent install (`C:\Users\Hendrik\Code\leafcutter\.leafcutter\scripts\`, deployed
    2026-10-25 12:00 UTC) carries this fix.
  - **Nothing tells the two copies apart:** `MAKER_VERSION = "1"` in both
    (`templates/scripts/worktree_git.py`:46), and the ok answer
    (`templates/scripts/worktree.py`:140-154) carries no maker build or source commit.

## Symptom

`worktree.py ensure` for a new workspace answers `status ok`, `workspace_action: created`, with
`base_commit` equal to the hub's current main. In the workspace, `git log -1` shows an older
main, `git status` shows the newer main's changes as staged, and `git diff --cached <base_commit>`
is empty: the index and files are the new main, HEAD is the old one.

## Mechanism

Read from the scratch workspace's reflogs (times UTC, 2026-10-25):

1. **20:52:15 — clone.** `clone: from C:\Users\Hendrik\Code\leafcutter\leafcutter-ai`, whose
   local `main` was `1a5c47cc3`. HEAD and the seeded `origin/main` are `1a5c47cc3`.
2. **20:52:19 — the maker's hub fetch.** `refs/remotes/origin/main`: `1a5c47cc3 → 5e5a37380`,
   "fetch --prune origin: fast-forward". The maker reads `origin/main` here as `base_commit`
   (`5e5a37380`, which is what the answer reported).
3. **20:52:28 — an outside fetch rewinds it.** `refs/remotes/origin/main`: `5e5a37380 →
   1a5c47cc3`, "fetch: storing head". `1a5c47cc3` is the main checkout's own `main`, so this
   fetch read the main checkout, not the hub. The branch config also carries
   `vscode-merge-base=origin/main`, so VS Code's Git extension was watching the new clone; its
   `git.autofetch` is the cause the fix commit names for the same rewind.
4. **20:52:32 — the checkout by name.** The branch log says `branch: Created from origin/main`
   (`0000000 → 1a5c47cc3`) and the branch has `remote=origin`, `merge=refs/heads/main`: a
   tracking `checkout -B <branch> origin/main`, exactly the in-repo copy's :86. The fixed maker
   would have logged a SHA start point, set no upstream, and refused on `verify-checkout`.
5. **The set-aside staged the gap.** With HEAD on `1a5c47cc3` and the reported base `5e5a37380`,
   the index ended up holding `5e5a37380`'s tree (the fix commit describes the old set-aside as
   re-staging this gap), and the maker answered ok.

Which `worktree.py` the caller ran is not recorded anywhere in the workspace; the conclusion
that it was the in-repo copy rests on step 4 matching that copy's code and not the fixed one.

## Detection

In a new workspace: `git rev-parse HEAD` differs from the answer's `base_commit`, or
`git diff --cached --stat` is non-empty right after `ensure`. In the reflog,
`branch: Created from origin/main` on the new branch, or a `fetch: storing head` that moves
`origin/main` backwards, is this issue. To check an install: a `worktree.py` whose
`_start_line` / `build_line` runs `checkout -B <branch> origin/main` (no `--no-track`, no SHA) is
the pre-fix maker.

## Workaround

Run the maker from the workspace-parent install (`C:\Users\Hendrik\Code\leafcutter\.leafcutter\scripts\worktree.py`),
not from `leafcutter-ai/.leafcutter/`. In a workspace already affected, check
`git diff --cached <base_commit>` is empty, then `git reset --soft <base_commit>` (or reset and
re-fetch).

## Suggested fix

Directions only; nothing here is applied.

- **Remove or rebuild the stale copy.** The in-repo install `leafcutter-ai/.leafcutter/` is
  planned for deletion once the BO-4300 workspace-maker work has fully merged; until it is
  deleted, rebuild it so it carries `1d316e0a0`, and rebuild it again whenever the maker changes.
- **Make the maker's build visible.** Bump `MAKER_VERSION` on behaviour changes, or put the
  maker's source commit in the ok answer and the ready marker, so a stale copy is visible in its
  own answer. A maker could also refuse when its own files differ from the hub main's
  `templates/scripts/worktree*.py`.
- **Report HEAD in the answer.** Adding `head_commit` (the SHA HEAD stands on when the answer is
  written) next to `base_commit` would have made both occurrences visible at once, whichever copy
  answered.

**Related.** `1d316e0a0` / PR #1351 fixed this race in the maker's source; this entry is about a
copy of the maker that predates the fix still being runnable. `KI-BO-20260928-fast-lane-worktree-step-runs-another-clones-script`
is the same class of problem from the other side: a step running a different checkout's copy of
a script than the one intended.

**Pattern:** a fixed defect still reachable through an older installed copy of the same tool, with
no version in the tool's answer to show which copy answered.
