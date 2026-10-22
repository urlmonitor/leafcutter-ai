---
title: "How to clear a workspace"
description: "How a person finds the workspace for a piece of work, asks the workspace maker to clear it, reads the unsent-work refusal, delivers that work first, or authorises its loss up front with a discard token."
type: how_to
category: how-to
status: active
created: 2026-10-13
last_updated: 2026-10-13
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

## Other refusals

A `PROCESS_HOLDS_FILES` answer means a program is using files in the folder: close it and
ask again. Other codes are in [the answer reference](../reference/workspace-maker-answer.md).
Quote the path, since it may contain spaces or backslashes. Do not delete the folder by hand; the maker's registry would still list it.
