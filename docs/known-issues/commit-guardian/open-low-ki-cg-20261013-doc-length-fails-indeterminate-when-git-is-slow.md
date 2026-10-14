---
title: "KI-CG-20261013-doc-length-fails-indeterminate-when-git-is-slow — check-doc-length refuses a commit as INDETERMINATE when one read-only `git cat-file -e` probe takes longer than the shared 15-second timeout, which happened under machine load from about 98 concurrent git processes, while the same call takes 0.06 s idle"
description: "low — check-doc-length resolves previous lengths through _file_size_ratchet: a full `git ls-tree -r HEAD`, then for every staged doc and every parent `git cat-file -e` plus `git show`, twice (lines and sections), each a separate process with a fixed 15 s timeout. A timeout raises PreviousLengthSourceError and the hook exits 2 INDETERMINATE. Observed during the BO-4300 drive while VS Code's git extension ran about 98 git processes across many worktrees. The fail-closed choice is correct; one slow probe failing the whole commit with no retry is not. Same constant as KI-CG-20261012 part (b), different hook and trigger: no merge, a handful of files, outside load."
type: reference
category: reference
status: active
created: '2026-10-13'
last_updated: '2026-10-13'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
  - docs/known-issues/commit-guardian/open-high-ki-cg-20261012-merge-precommit-checks-conflicts-only-and-file-size-times-out.md
---

# KI-CG-20261013-doc-length-fails-indeterminate-when-git-is-slow — one slow git probe refuses the commit

> Filed 2026-10-13 from the BO-4300 drive. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`).

- **Severity:** low. It fails closed with a clear message, and a retry when the machine is quieter
  passes. But the refusal names a timeout rather than a doc, so an agent can read it as a defect in
  the staged docs. On a busy multi-worktree machine it recurs.
- **Status:** open, no AC. Code path verified on `origin/main` `964f23a60`. The timeout is from the
  coordinator's session account.
- **Occurrences:** 1 (BO-4300 epic worktree, 2026-10-12/13).
- **First seen:** 2026-10-13 · **Last seen:** 2026-10-13
- **Where:**
  - `templates/scripts/commit_guardian/check_doc_length.py:410-412` calls `resolve_doc_ratchet` and
    returns its exit 2. That function prints `INDETERMINATE: reason=...` on any `PreviousLengthSourceError`.
  - `templates/scripts/commit_guardian/_doc_length_ratchet.py:243-290` (`resolve_doc_ratchet`): one
    `resolve_head_matching_paths` (`git ls-tree -r --name-only HEAD`), then `resolve_previous_lengths`
    twice, once for lines and once for sections (`:284-285`).
  - `templates/scripts/commit_guardian/_file_size_ratchet.py`: `_SUBPROCESS_TIMEOUT_SECONDS = 15`
    (`:65`). `_run_git` (`:464-491`) converts a `TimeoutExpired` into `PreviousLengthSourceError("the
    previous lengths could not be read: git could not be invoked (...)")`. `get_previous_content` runs
    `git cat-file -e <rev>:<path>` through it (`:640`), then `git show` (`:516-526`).

## Symptom

`check-doc-length` exited 2:

```text
INDETERMINATE: reason=the previous lengths could not be read: git could not be invoked (Command '['git', 'cat-file', '-e', ...]' timed out after 15 seconds)
```

At that moment VS Code's git extension was running about 98 git processes across the open worktrees.
Run again on an idle machine, the same `git cat-file -e` returned in 0.06 s and the hook passed.

## Mechanism

- **Many small processes.** For each staged doc and each parent revision, the hook starts
  `cat-file -e` and `show`, and it does that twice, because lines and sections are resolved
  separately. One commit touching k docs starts about 4k + 1 git processes. Each has its own fixed
  15-second budget.
- **One slow call decides the verdict.** There is no retry. A timeout is reported exactly like an
  unreachable repository. That is the right choice for "git is missing", and the wrong one for "git
  was slow once".
- **The load came from outside.** Unlike `KI-CG-20261012-merge-precommit-checks-conflicts-only-and-file-size-times-out`
  part (b), this was not a large merge. The hook's own process count was small. So scaling the timeout
  with the number of files would not have helped.

## Detection

An `INDETERMINATE` from `check-doc-length` (or `check-file-size`) whose reason ends in `timed out after
15 seconds`, on a commit with few staged files. Check `tasklist | findstr git` (or `pgrep -c git`) at the
time.

## Workaround

Retry the commit once the machine is quieter. Closing the editor's git integration for unused worktrees
also helps.

## Fix direction

- **Retry a timed-out read-only probe once** (`cat-file -e`, `show`, `ls-tree`) before failing closed,
  and say in the INDETERMINATE text that it timed out twice.
- **Give read-only probes a longer budget** than 15 s. They cannot change anything, and failing closed
  on them costs a whole commit.
- **Batch the reads** with one `git cat-file --batch-check` / `--batch` process for every `<rev>:<path>`,
  and read each blob once for both lines and sections. That removes most of the processes, and with
  them most of the exposure. It is the same fix `KI-CG-20261012` proposes for `check-file-size`, in the
  shared helper, so one change covers both hooks.

**Related.** `KI-CG-20261012-merge-precommit-checks-conflicts-only-and-file-size-times-out` part (b):
the same 15-second constant in the same helper, reached through `check-file-size` on a 4,800-file merge.

**Pattern:** a fail-closed gate that cannot tell "the source is unreachable" from "the source was slow
once".
