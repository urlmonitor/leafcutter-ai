---
title: "KI-CG-20261012-merge-precommit-checks-conflicts-only-and-file-size-times-out — during a merge, pre-commit hands filename-driven hooks only the conflicted files, in the preflight and the real commit alike, and check-file-size's per-file 15-second git reads can time out on a large merge, so a passing preflight neither covers the staged set nor predicts the commit"
description: "high — while MERGE_HEAD and MERGE_MSG exist, pre-commit 4.6.2 selects 'merge-conflict files only' for both 'pre-commit run' and the real commit hook. On three recent merges that set held 0, 0 and 2 files, against 11 to 645 files changed from one parent, so a merge-mode Passed says nothing about most of the staged set. check-file-size reads the staged set itself, with two git subprocesses per file per parent and a 15-second timeout each. On the 2026-10-12 merge of origin/main into fast-lane/bo-2400f-5-iii (about 4,800 staged files), the preflight passed, the commit failed INDETERMINATE on a timeout, and a retry passed at 31fae105."
type: reference
category: reference
status: active
created: '2026-10-12'
last_updated: '2026-10-12'
components:
  - commit_guardian
  - precommit_hooks
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
  - docs/known-issues/commit-guardian/open-high-ki-cg-20260927-file-size-hook-read-another-worktrees-index.md
  - docs/known-issues/commit-guardian/open-low-ki-cg-20260928-file-size-ratchet-refuses-when-both-parents-grew.md
---

# KI-CG-20261012-merge-precommit-checks-conflicts-only-and-file-size-times-out — a merge-mode preflight neither covers the staged set nor predicts the commit

> Filed 2026-10-12 from the merge of origin/main into `fast-lane/bo-2400f-5-iii`.
> Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`high`); the original grading is the
> `**Severity:**` line below.

- **Severity:** high, for part (a). A merge-mode run reports `Passed` or `(no files to check)
  Skipped` for filename-driven hooks after showing them only the conflicted files. It reads as a
  verdict on the staged set, and here it was taken as one. Part (b) fails closed and on its own
  would be low: a refusal that a retry clears.
- **Status:** open, no AC.
- **Occurrences:** 1 (2026-10-12). The preflight passed in merge mode, the first commit attempt
  failed INDETERMINATE, and the retry succeeded at `31fae105`.
- **First seen:** 2026-10-12 · **Last seen:** 2026-10-12
- **Where:**
  - pre-commit 4.6.2 (`.venv/Lib/site-packages/pre_commit/`): `commands/run.py:253-271`
    (`_all_filenames`, merge branch at :268-269); `git.py:96-101` (`is_in_merge_conflict`) and
    :114-132 (`get_conflicted_files`); `commands/hook_impl.py:237-238` (the real `pre-commit` hook
    builds its run with no file list, so it takes the same branch).
  - `.pre-commit-config.yaml:470-476`: `check-file-size` is `pass_filenames: false`,
    `always_run: true`.
  - `templates/scripts/commit_guardian/check_file_size.py` on origin/main `e93eda09a` (GE-127a-1 /
    GE-127b-1). It reads its own staged set with `git diff --cached --name-status` (:195) and
    resolves previous lengths for every covered path at every parent (:557-558).
  - `templates/scripts/commit_guardian/_file_size_ratchet.py`: `_SUBPROCESS_TIMEOUT_SECONDS = 15`
    (:65); `resolve_previous_lengths` loops over paths and revisions (:822-825); `get_previous_content`
    runs `git cat-file -e` (:640) and then `_read_blob_bytes`, whose `git show <rev>:<path>` timeout
    becomes the INDETERMINATE text (:516-526). The deployed `.leafcutter/` copies are identical.

## Symptom (a): merge mode

While `MERGE_HEAD` and `MERGE_MSG` exist, `pre-commit run` prints `Checking merge-conflict files
only.` and hands hooks the conflicted files from `MERGE_MSG`, plus the files where the staged tree
differs from **both** parents (`git diff --name-only -m <tree> HEAD MERGE_HEAD`).

That set is small. The same command applied to three recent merge commits on main gives:

| Merge | pre-commit's merge set | Differs from parent 1 | Differs from parent 2 |
|---|---|---|---|
| `e93eda09a` | 0 | 12 | 254 |
| `1f577f167` | 0 | 87 | 645 |
| `3f2abe1b3` | 2 | 11 | 82 |

**The real commit is no different.** The filing note assumed that the merge commit would run the
hooks over the whole staged set. pre-commit 4.6.2 does not. The installed shim runs
`hook-impl --hook-type=pre-commit`, which builds the run with no file list
(`hook_impl.py:237-238`). The run reaches the same `is_in_merge_conflict()` branch, so
filename-driven hooks see the same small set in the commit as in the preflight. A direct
`git commit` could not be used to confirm this, because it is blocked outside the commit agent.
This was read from source.

Hooks that read the staged set themselves (`pass_filenames: false`) examine all of it in both runs.
`check-file-size` is one of them, which is why it alone did the full work on this merge.

So for filename-driven hooks, a merge-mode preflight predicts the commit correctly, but neither
examines the roughly 4,800 files the merge brings in. A preflight run with `--files <staged set>`
leaves merge mode (`args.files` is checked before the merge branch). It then runs those hooks over
every staged file: more than the commit will check, and far slower.

## Symptom (b): timeout under load

For each covered staged file and each parent revision, `check-file-size` starts `git cat-file -e`
and then `git show <rev>:<path>`, each with a 15-second timeout. A merge has two parents, so a
merge of about 4,800 staged files means thousands of git processes. On a busy machine (this merge,
plus parallel worktree activity) one call timed out, and the hook failed closed:

```text
INDETERMINATE: reason=the previous length for '<path>' at '<sha>' could not be read: git could not be invoked (... timed out after 15 seconds)
```

Failing closed is correct. The fixed per-call timeout is what makes large merges flaky.

## Detection

- (a) `Checking merge-conflict files only.` in any preflight output, or a merge in progress
  (`git rev-parse -q --verify MERGE_HEAD`) when the preflight ran.
- (b) An `INDETERMINATE` refusal from `check-file-size` whose reason ends in `timed out after 15
  seconds`.

## Workaround

- Retry once for (b).
- For a merge, don't treat the merge-mode preflight as covering the staged set. It covers the
  conflicted files. If the incoming files must be checked, run `pre-commit run --files` over them
  explicitly. That is a different check from the one the commit will run.

## Suggested fix

- **(a)** State merge mode in the commit-agent and orchestrator preflight guidance: what it covers,
  that the real commit uses the same selection, and that `--files` leaves it. Have a preflight that
  detects `MERGE_HEAD` say so in its own result line, so the partial verdict is visible.
- **(b)** Read previous lengths in one batch, for example one `git cat-file --batch` process fed
  every `<rev>:<path>`, instead of two processes per file per parent. Or scale the timeout with the
  number of files, as done-proof's pytest budget does (`_resolve_pytest_timeout_seconds`). Batching
  also removes most of the load that caused the timeout.

**Related.** `KI-CG-20260927-file-size-hook-read-another-worktrees-index` is another way the same
hook's per-file git queries misbehave under concurrent worktree activity.
`KI-CG-20260928-file-size-ratchet-refuses-when-both-parents-grew` covers the same hook's
merge-parent handling.

**Pattern:** a preflight whose scope is chosen by the tool's hidden mode, read as if it covered
everything that will be committed.
