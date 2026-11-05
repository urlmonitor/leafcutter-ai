---
title: "How to clear a workspace"
description: "How a person finds the workspace for a piece of work, asks the workspace maker to clear it, reads the unsent-work refusal, delivers that work first, or authorises its loss up front with a discard token, and what to do when a running program, a half-cleared workspace, an unknown folder or a workspace off its line of work causes a refusal."
type: how_to
category: how-to
status: active
created: 2026-10-13
last_updated: 2026-11-02
components:
  - worktree_manager
  - build_orchestration
related_docs:
  - docs/how-to/get-a-workspace.md
  - docs/reference/workspace-maker-answer.md
  - docs/architecture/components/worktree-manager.md
---

# How to clear a workspace

Clear a workspace only through the workspace maker. It checks that nothing undelivered is
lost, and it removes the whole folder so nothing is left half-deleted. For how a workspace
is made in the first place, see [How to get a workspace](get-a-workspace.md).

## 1. Find the workspace

```bash
python /absolute/path/to/scripts/worktree.py locate --kind <kind> --slug <slug>
```

A ready answer gives `workspace_path`. That is the location to clear.

## 2. Ask for it to be cleared

```bash
python /absolute/path/to/scripts/worktree.py remove --path "<workspace-path>"
```

If nothing in the workspace is undelivered, the answer is `"status": "ok"` and the workspace
is gone.

## 3. If the answer is UNSENT_WORK

The maker refuses (exit code 2, `"code": "UNSENT_WORK"`) and leaves the workspace as it was.
The answer lists exactly what would be lost, under `unsent`:

- `commits`: unpushed commits on the workspace's line of work.
- `files`: uncommitted files, including new untracked ones.

It also carries a `discard_token`.

**To keep the work:** deliver it first. Commit the uncommitted files, push the unpushed
commits to the shared project, then repeat step 2.

**To throw the work away:** repeat the same request and add the token from that refusal,
which authorises the loss up front:

```bash
python /absolute/path/to/scripts/worktree.py remove --path "<workspace-path>" --discard-token <discard-token>
```

The token is one-time and bound to this workspace and to exactly the unsent work the refusal
listed. It is valid only on the `remove` request for that workspace, and only while that work
is unchanged. If anything changed, the maker refuses again with a fresh token. Never store
it, and never put it in an environment variable or a config setting; read it from the
refusal each time. `--force` is accepted but does nothing.

## If a program is running in the workspace

A refusal with `"code": "PROCESS_HOLDS_FILES"` names the programs it found in `holders`.
Nothing was deleted. Leave that folder (close any terminal or editor opened in it) or stop
the named program, then repeat step 2.

If the refusal says the program check is unavailable, nothing was deleted either: the maker
will not clear a workspace unless it can check for running programs. Ask again once the check
works, and report it if the refusal persists.

If the message says some items could not be deleted, a program still holds them. Stop it and
ask again; the clearing continues where it stopped.

## If an earlier clearing stopped part-way

A workspace whose repository is already gone is half-cleared. Ask again with the same request
as in step 2 and the maker finishes it. If the folder holds no files, it is simply finished.

If it still holds files, the refusal is `UNSENT_WORK` and lists them under `unsent`. They
cannot be checked against the shared project, so they would be lost. Save any you want to
keep elsewhere first. To accept the loss, repeat the request with the `discard_token` from
that refusal, as in step 3. Read the token from that refusal each time and never store it.

## If the folder has no workspace record

A folder that holds files but has no workspace record is refused with `"code": "NOT_FOUND"`
and the files under `files`. The maker cannot tell it is a workspace of this project, so it
changed nothing and offers no token. Check that you have the right path: run step 1 again and
use the `workspace_path` it gives.

## If the workspace is off its line of work

A detached workspace is cleared or refused like any other. If the refusal is `UNSENT_WORK` and
names commits under `unsent.commits`, deliver them first. A commit counts as delivered only
once it is on the shared project's `main` or on the workspace's own branch (the `branch` that
step 1 reports), so push it to that branch. Run this inside the workspace:

```bash
git push origin HEAD:refs/heads/<branch>
```

If the push is refused because that branch has moved on, deliver the commits through a pull
request into `main` instead. Then repeat step 2; the next answer no longer lists them.

## Other refusals

Every other code is in [the answer reference](../reference/workspace-maker-answer.md), which
describes each refusal and the fields it carries. Quote the path, since it may contain spaces
or backslashes. Do not delete the folder by hand; the maker's registry would still list it.
