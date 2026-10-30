---
title: "KI-BO-20261030-maker-cannot-remove-a-half-removed-workspace — a workspace whose deletion failed partway can no longer be removed through the maker, because every later remove first needs a git fetch that the half-deleted repo cannot run"
description: "medium — worktree.py remove deletes the folder after its safety checks; when the rmtree fails partway (Windows file lock) the .git object store is left broken, every retry refuses FETCH_FAILED before any deletion, and the discard token is only issued after a successful fetch. The only way out is a manual delete, which the maker-only rule forbids."
type: reference
category: reference
status: active
created: '2026-10-30'
last_updated: '2026-10-30'
components:
  - worktree_manager
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/how-to/get-a-workspace.md
---

# KI-BO-20261030-maker-cannot-remove-a-half-removed-workspace — a workspace whose deletion failed partway can no longer be removed through the maker, because every later remove first needs a git fetch that the half-deleted repo cannot run

- **Severity:** medium. No work is lost by itself, but the maker leaves a workspace it can no
  longer clear. The only way out is a hand delete, which bypasses the maker. That is exactly
  what the one-maker rule exists to prevent, and a hand delete has no unsent-work check.
- **Status:** open. No AC.
- **Occurrences:** 1 (`worktree.py remove` of the fast-lane workspace `fastlane/fin-100c-15`,
  2026-10-29, Windows 11, after PR #1355 merged)
- **First seen:** 2026-10-29 · **Last seen:** 2026-10-29
- **Where:** `templates/scripts/worktree_remove.py` at origin/main `d62440669`: the remove
  sequence at `:402` (`_authorise`, which runs `unsent_work` and so the fetch) and `:414`
  (`_delete_tree`); the deletion in `delete_whole_folder()` (`:257`, rmtree at `:268`); the
  fetch refusal in `unsent_work()` (`:155`, refusal at `:164`).

## Symptom

1. First `remove --path <ws>`: it passed the unsent-work check and the holding-programs check,
   then the rmtree failed partway with
   `[WinError 145] Das Verzeichnis ist nicht leer: '\\?\<ws>\.git\objects\02'`. The answer was
   `PROCESS_HOLDS_FILES` ("a program may hold files"). About 19,500 files remained, including
   a `.git` with part of its object store gone.
2. The same `remove` a few minutes later: `FETCH_FAILED`, "The step 'git fetch origin' failed …
   cannot tell what is unsent". In the workspace, `git status` gave `fatal: bad object HEAD`, and
   `git fetch origin` gave `fatal: pack has 4724 unresolved deltas` /
   `fetch-pack: invalid index-pack output`.
3. No process named the workspace in its command line. The lock was most likely a short-lived
   scanner (Defender or the search indexer) on a git object file.

## Why the maker cannot recover

- The rmtree runs **last**, after the safety verdict (`:402` then `:414`). It walks `.git` with
  everything else, so a failure partway leaves a repo whose object store is broken.
- Every later `remove` re-runs `_authorise` → `unsent_work` → `git fetch origin` (`:164`) before
  it deletes anything. A broken object store cannot fetch, so the answer is always
  `FETCH_FAILED`. Unknown is correctly never treated as "nothing unsent".
- `--discard-token` cannot help. The token is computed only from an unsent-work verdict
  (`discard_token()`, issued in the `UNSENT_WORK` refusal), and that verdict needs the fetch.
- `--force` is accepted and ignored by design.

So the maker has no path from this state to "removed". A real `PROCESS_HOLDS_FILES` with the
tree still intact is retryable, but a deletion that got partway is not.

## Detection

A `remove` that answers `PROCESS_HOLDS_FILES` with the message
`Could not remove all of <ws> (a program may hold files): …` (the `delete_whole_folder` text,
not the earlier `Programs are running in or holding files of …` text). After it, the workspace
folder still exists and `git -C <ws> status` fails with `bad object HEAD`. Any retry then
answers `FETCH_FAILED`.

## Workaround

Confirm by hand that nothing is unsent: the branch is on origin, or its PR has merged. In this
occurrence `717fd0c` was on origin and merged as `4669738`. Then delete the folder by hand
(`Remove-Item -LiteralPath <ws> -Recurse -Force`) and check that `worktree.py list` no longer shows
it. A short retry did not help here, because by the time of the retry the fetch was already
broken.

## Suggested fix

Any one of these closes the hole. The first is the smallest.

1. **Retry the rmtree before answering.** On a Windows lock error, wait briefly and retry a few
   times inside `delete_whole_folder()` before returning the reason. Transient scanner locks
   usually clear within a second.
2. **Delete `.git` last.** Remove the work tree first and `.git` after it, so a failure partway
   is most likely to leave `.git` intact and the next `remove` can still fetch and verify.
3. **Remember a passed verdict.** Before the rmtree, write a small "verdict passed: nothing
   unsent at <sha>" record outside the folder (or in the maker's landing root). A later `remove`
   of the same path that finds the record and a broken repo resumes the deletion without
   fetching. This is safe because the verdict was already reached on an intact repo.
