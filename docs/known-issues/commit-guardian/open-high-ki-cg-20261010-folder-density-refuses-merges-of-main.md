---
title: "KI-CG-20261010-folder-density-refuses-merges-of-main — check-folder-density takes its before-count from HEAD alone, so merging origin/main into a branch is refused for every folder that main itself took over the limit"
description: "high — since the hook could first refuse (on main from 2026-10-09), any merge of origin/main into a branch that predates a folder crossing the 15-file limit on main is refused for content the merge did not author. Four folders crossed on main in two days, each through a GitHub server-side merge that runs no local hook. Three merges of main were refused on 2026-10-10: two needed a user-run SKIP=check-folder-density, one was abandoned. The fix is already ticketed on main (see Status)."
type: reference
category: reference
status: active
created: '2026-10-10'
last_updated: '2026-10-10'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
  - docs/known-issues/commit-guardian/open-low-ki-cg-20260909-gate-folder-density.md
  - docs/known-issues/commit-guardian/resolved/resolved-high-ki-cg-20260908-ratchet-reads-pre-merge-head.md
  - docs/known-issues/commit-guardian/open-high-ki-cg-20260914-contract-guard-crashes-on-diff-bytes.md
  - tickets/00_inbox/TICKET-20261010-FolderDensityMergeCommit.md
---

# KI-CG-20261010-folder-density-refuses-merges-of-main — a merge of main is judged as if the branch had authored main's dense folders

> Filename severity is the three-level index bucket (`high`); the original grading is the
> `**Severity:**` line below.

- **Severity:** high. The refusal is loud and nothing wrong lands. But it refuses a merge of
  `origin/main` into any branch that predates a folder crossing the limit on main, for content the
  merge did not author. Every way out needs the user: a `SKIP=check-folder-density` commit the user
  runs, restructuring main's folder inside the merge, or abandoning the merge. `/finalize-feature`
  merges `origin/main` into the worktree before it merges the PR, so the standard landing path
  hits it. Not graded blocker: a PR without conflicts can still be merged server side, which runs
  no local hook. Same shape and grade as the resolved `KI-CG-20260908-ratchet-reads-pre-merge-head`
  (`check-file-size`).
- **Status:** open, no AC. The fix is ticketed on main as
  `tickets/00_inbox/TICKET-20261010-FolderDensityMergeCommit.md` (`status: todo`, priority high).
  The mechanism is verified by reading the hook on `origin/main` `d03830e7c` and by running the
  hook's own counting and classification functions over the real trees (see Mechanism, step 3).
- **Occurrences:** 3 refused merges of main, all on 2026-10-10:
  - `docs/pol-git-001`: merge `23340650a`, committed with a user-run skip.
  - `acs/decision-lifecycle`: merge `753562dc9`, committed with a user-run skip.
  - `ki/bo4300-drive-findings`: refused, and the merge was dropped. The PR went in as one commit
    re-cut from main (`dfa6da64f` on `6b400a8f6`).
- **First seen:** 2026-10-10 · **Last seen:** 2026-10-10
- **Where:** `templates/scripts/commit_guardian/check_folder_density.py` on `origin/main`
  `d03830e7c`:
  - BEFORE is `git ls-tree -r HEAD` (`get_all_tracked_files`, :124-170; the call at :160-165).
  - The staged set is `git diff --cached --name-status` against HEAD (:53-81).
  - `_classify_folders` (:277-302) blocks any affected folder that is over the limit in the index
    and not over it in BEFORE.
  - Nothing in the file reads `MERGE_HEAD`.

## Symptom

```text
❌ FOLDER TOO DENSE: docs/acceptance-criteria/decision-kernel/DK-600-decide-once-reuse/
   Non-markdown files: 54 (limit: 15)
```

This came from merging 33 commits of `origin/main` (up to `6b400a8f6`, the merge of PR #1004) into
`ki/bo4300-drive-findings` (tip `4f3707604`). The branch never touched that folder. It went from 0
to 54 files in `6b400a8f6` itself.

## Mechanism

1. **BEFORE is the branch side only.** During a merge, HEAD is the branch's pre-merge tip. A folder
   that main added or grew after the branch point is absent or small there.
2. **Every file main brought is "staged".** `git diff --cached` compares the index with HEAD, so all
   of main's additions are A or M entries, and their folders count as affected.
3. **So main's crossings read as this commit's crossings.** BEFORE is at most 15 and AFTER is over
   15, so the folder is a violation. Verified by passing the trees of `4f3707604` (HEAD) and
   `6b400a8f6` (the merge result) to the hook's own `count_files_per_folder` and
   `_classify_folders`: exactly one violation, DK-600 at 54; the other dense folders only warn. DK-600 is
   also over the limit on the `6b400a8f6` side, so grandfathering on MERGE_HEAD would have cleared
   it.
4. **The refusal became reachable on 2026-10-08.** Until `d8cd00a9d` (GE-120h-3, on main through
   PR #1067, `be81681d4`, 2026-10-09 07:12 UTC), BEFORE came from `git ls-files`. That is the index,
   so BEFORE equalled AFTER and the hook could only warn (`KI-CG-20260909-gate-folder-density`).
   The fix made refusal real but did not cover merges. The sibling ratchets already do:
   `_file_size_ratchet.py` (`_merge_head_path`, :689), `_complexity_ratchet.py` (the highest score
   across HEAD and every MERGE_HEAD parent) and `_ac_governance_baseline.py` all read MERGE_HEAD.

It also works against the hook's own criterion. GE-120h-3 (`GE-120h-3.yaml:26-30`) says a commit
that does not make the repository's existing state worse is not refused for that state, including
"the directories that already hold more files than the density limit permits". A merge of main does
not make the repository's state worse.

## How a 54-file folder reached main past the hook

- **The merge into main ran no local hook (verified).** `6b400a8f6` is a GitHub merge (committer
  `GitHub <noreply@github.com>`), so no pre-commit ran on it. CI does not run
  `check-folder-density`: the `pre-commit run` lines in `.github/workflows/ci.yml` (:640-645,
  :743-746) name only AC-store hooks.
- **On its branch the folder was created before the hook could refuse (verified).** `e6fc5baec`
  (2026-10-06, the DK-300 to DK-600 renumber) took it from 0 to 54 in one commit. The hook on that
  branch still read BEFORE from `git ls-files`, so it could only warn. Later branch commits (for
  example `9fedcb947`, 2026-10-10) changed files in a folder already over the limit, which is a
  warning by design.
- **The other three crossings since the hook was armed** also reached main through GitHub merges
  (verified, committer GitHub):
  - `docs/acceptance-criteria/build-orchestration/BO-4400-nothing-accumulates/`, 0 to 49 (PR #1098,
    `e3a98fdf4`). It was authored in `46c81167b` with a user-authorized `SKIP=check-folder-density`
    (verified, commit message).
  - `docs/product-truth/mockups/leafcutter/`, 14 to 16 (PR #1086). It crossed in `46255a446`,
    before that branch had the armed hook (verified).
  - `scripts/ci/`, 15 to 16 (PR #1084). It crossed in `fa428f307`, whose tracked hook was already
    armed. How that commit passed is not recorded. Inferred: the worktree's installed `.leafcutter`
    copy was older than its templates (`KI-BP-20261009-epic-worktree-install-goes-stale-per-ticket`).

So any branch forked before 2026-10-10 11:44 UTC is refused on its next merge of main for DK-600.
A branch forked before 2026-10-09 is also refused for the other three.

## A layout conflict underneath

The AC store keeps one flat folder per L0 tree, and the cap counts the `.yaml` leaves. Two
authoring commits record that conflict and were committed with a user-approved skip:

- `46c81167b`: "AC trees are stored flat per L0 folder (no nested AC folders exist; BO-4300 holds
  68)".
- `47589a326`: "115 of its 179 folders are already over the limit. Excluding
  docs/acceptance-criteria/ from the density check will go through its own AC."

So an AC tree with more than 15 leaves is refused once when it is authored, and then again on
every branch that merges main after it lands. A search of the AC store on `d03830e7c` for
"density" found no AC for that exclusion yet.

## Workaround

- Have the user run the merge commit with `SKIP=check-folder-density`, stating in the message that
  every flagged folder is dense on main (as `753562dc9` does). All other hooks still run.
- Or re-cut the branch from current main and replay its own commits (as
  `ki/bo4300-drive-findings-v2` did).

## Fix direction

- As the ticket scopes it: when `MERGE_HEAD` exists, take each folder's BEFORE as the maximum over
  HEAD and every MERGE_HEAD parent. Resolve the file with `git rev-parse --git-path MERGE_HEAD` and
  read every line, as `_file_size_ratchet._merge_head_path` does, so octopus merges and linked
  worktrees work. A violation is then only a folder that no parent had over the limit and the merge
  result has over it.
- Tests: a merge that brings in a folder already dense on MERGE_HEAD passes. A merge where neither
  parent is over the limit but the result is, is refused. An ordinary commit is unchanged.
- Separately, decide whether the AC store is subject to the cap at all (see above).

**Related.**

- `KI-CG-20260909-gate-folder-density`: the opposite defect in the same hook. BEFORE was the index,
  so the hook could never refuse. `d8cd00a9d` fixed that, and this defect is what the fix exposed.
- `KI-CG-20260908-ratchet-reads-pre-merge-head` (resolved): the same defect in `check-file-size`,
  and the fix pattern to reuse.
- `KI-CG-20260914-contract-guard-crashes-on-diff-bytes`: the next hook that failed on the same merge.

**Pattern:** a ratchet whose "before" is one parent of a commit that has two.
