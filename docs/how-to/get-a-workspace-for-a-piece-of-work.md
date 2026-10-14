---
title: "How to get a workspace for a piece of work, check it, find it again, and remove it"
description: "Use the one workspace maker (worktree.py) to get a ready, independent workspace for one piece of work, re-check it, find it later, and delete it, and know what to do on each refusal code."
type: how-to
status: active
created: 2026-10-14
last_updated: 2026-10-14
components:
  - worktree_manager
  - build_orchestration
related_docs:
  - docs/architecture/adrs/ADR-070-single-workspace-maker-and-resolver.md
  - docs/architecture/components/worktree-manager.md
related_code:
  - templates/scripts/worktree.py
  - templates/scripts/workspace/workspace_core.py
  - templates/scripts/workspace/workspace_checks.py
  - templates/scripts/workspace/workspace_create.py
  - templates/scripts/workspace/workspace_root.py
---

# How to get a workspace for a piece of work, check it, find it again, and remove it

Every route that needs an isolated copy of the project (a long-running build, a quick fix, a requirements session, an agent, a person at a terminal) asks the same maker, `worktree.py`, so each gets the same kind of workspace and the same answer shape back.

## Prerequisites

- A project installed with leafcutter, so the maker is deployed at `<project>/.leafcutter/scripts/worktree.py`.
- Python 3 on the path. The maker is stdlib-only.
- The main checkout has an `origin` remote. That remote is the hub the workspace is cloned against.
- A `scripts/build.py` in the project and an install config, so the workspace can build its own install.
- Read [ADR-070](../architecture/adrs/ADR-070-single-workspace-maker-and-resolver.md) for why the maker works this way. This guide covers only the commands.

## Steps

Every command prints exactly one JSON object on stdout and exits 0 only when `"status": "ok"`. The maker never reads stdin and never prompts. Run it from any directory. Pass `--repo-root <absolute path of the main checkout>` when your current directory is not inside the project. Without it, the maker finds the project from the current directory.

### Step 1 — Find the maker's path

```bash
python <project>/.leafcutter/scripts/worktree.py where
```

The answer's `maker_path` is the absolute path to use in every later command:

```json
{"status": "ok", "code": "OK", "verb": "where", "mechanism": "clone", "maker_version": "1.0.0", "maker_path": "/abs/path/to/scripts/worktree.py"}
```

### Step 2 — Ask for the workspace

Pick the kind that matches your work: `ticket`, `feature`, `ac`, `fastlane`, `epic`, or `scratch`. The slug is the identity of the work. The same kind and slug from any route give the same folder and the same branch.

```bash
python <maker_path> ensure --kind feature --slug my-change
```

To work on a ticket, also pass the ticket path from the main checkout (absolute or project-relative). `--ticket` is refused with `--kind scratch`.

```bash
python <maker_path> ensure --kind epic --slug MyEpic --ticket tickets/00_inbox/epics/EPIC-MyEpic/01_TICKET.md
```

Optional flags: `--repo-root <path>`, `--config-path <file>` (use this file as the build config instead of the one derived from the main install), and `--allow-stale-base` (accept the existing `origin/main` when the hub cannot be reached).

`ensure` is the only verb that creates. It is idempotent: asking again for the same work re-checks the existing workspace and does not rebuild it. The workspace lands in a `worktrees/` folder beside the main checkout.

### Step 3 — Read the answer

A ready workspace answers with `"status": "ok"`. Take the location from `workspace_path`:

```json
{
  "status": "ok", "code": "OK", "verb": "ensure", "mechanism": "clone", "maker_version": "1.0.0",
  "kind": "feature", "slug": "my-change", "branch": "feature/my-change", "state": "ready",
  "hub": "<hub url>", "project_root": "<main checkout>", "base_commit": "<sha>",
  "workspace_path": "<landing>/feature-my-change", "workspace_path_posix": "<same, forward slashes>",
  "worktree_path": "<same as workspace_path>",
  "origin_main_commit": "<sha>", "base_matches_origin_main": true,
  "checks": {"is_independent_repo": true, "not_main_checkout": true, "same_project": true,
             "branch_matches": true, "not_protected_branch": true, "base_is_fresh": true,
             "build_ok": true, "tree_clean": true, "precommit_config_present": true,
             "hooks_pre_commit_fired": true, "hooks_canary_rejected": true}
}
```

When you passed `--ticket`, the answer also carries `ticket_path_in_worktree` and `ticket_path_in_worktree_posix`. Work on the ticket only at that path, never at the main-checkout copy. The `checks` object also gains one `hooks_<stage>_fired` key for each further hook stage the workspace's own `.pre-commit-config.yaml` declares under `default_install_hook_types`.

### Step 4 — Re-check the workspace later

```bash
python <maker_path> verify --path <workspace_path>
```

`verify` returns the same ok answer shape with `"verb": "verify"`. Add `--kind <kind>` and `--slug <slug>` to also assert the workspace belongs to that work. It is documented as read-only, but on a clean tree it runs the canary, which makes and then undoes a commit of its own.

### Step 5 — Find the workspace again

Find one workspace by kind and slug, by branch, or by path:

```bash
python <maker_path> locate --kind feature --slug my-change
```

```bash
python <maker_path> locate --branch feature/my-change
```

```bash
python <maker_path> locate --path <workspace_path>
```

`locate` answers with the identity fields (kind, slug, branch, state, hub, project_root, base_commit, workspace_path, workspace_path_posix, worktree_path). It does not recompute `checks`.

To see every workspace for this project, scan the landing place's markers:

```bash
python <maker_path> list
```

The answer holds `"workspaces": [ ... ]`, one identity entry per workspace.

### Step 6 — Remove the workspace

```bash
python <maker_path> remove --path <workspace_path>
```

`remove` refuses with `UNSAVED_WORK` when the workspace has uncommitted changes or commits not on the pushed branch (or on `origin/main` when the branch was never pushed). Commit and push the work, or give up-front authorisation to throw it away:

```bash
python <maker_path> remove --path <workspace_path> --discard
```

Add `--delete-remote-branch` to also delete the workspace's branch on the hub before the folder is deleted. A successful remove answers with `"removed": true`.

## Verification

```bash
python <maker_path> locate --kind feature --slug my-change
```

Expected: a JSON object with `"status": "ok"`, `"verb": "locate"` and `"state": "ready"` while the workspace exists. After `remove`, the same command answers `"status": "error"` with `"code": "NOT_FOUND"` and exits 1. See Troubleshooting for any other code.

## Troubleshooting

An error answer has `"status": "error"`, a `"code"`, a `"verb"` and a `"message"`, and the process exits 1. Some also carry `workspace_path` or `checks`.

1. **`NOT_READY`.** At least one readiness check was not true. The `checks` object in the answer names which one. `tree_clean: false` also makes `hooks_canary_rejected` false, so an existing workspace holding uncommitted work answers `NOT_READY` on `ensure` and `verify`. Commit or stash the work, then run `verify` again. If a different check is false (for example `precommit_config_present` or a `hooks_*_fired` key), fix that ingredient in the workspace and run `verify` again.
2. **`WORKSPACE_INCOMPLETE`.** The folder exists but its marker is missing or not `ready`, typically from an interrupted `ensure`. Run `remove --path <path> --discard`, then run `ensure` again. A failed `ensure` cleans up its own half-made workspace, so this mostly follows a killed process.
3. **`BUILD_FAILED`.** The workspace's install build exited non-zero. The message ends with the tail of the build output. Fix the build problem (it runs `scripts/build.py --target-dir <workspace> --config-path <config>`), then run `ensure` again. The failed attempt left no folder behind.
4. **`FETCH_FAILED`.** The hub could not be reached to fetch `origin/main`, or to ask whether the branch already exists. Restore access to the hub and run `ensure` again. To accept the existing `origin/main` instead, add `--allow-stale-base`. The answer then has `base_matches_origin_main: false` unless the base happens to be current, and a warning about the hub goes to stderr.
5. **`NO_HUB`.** The main checkout has no `origin` remote. Add one to the main checkout, then run `ensure` again.
6. **`NO_CONFIG` or `NO_BUILD_ENTRY`.** The maker found no install config in the main checkout (`.claude/skills_config.json` or `.leafcutter/config/skills_config.json`), `--config-path` is not a file, or no `scripts/build.py` exists. Run the install build in the main checkout, or pass `--config-path <file>`.
7. **`NO_REPO` or `AMBIGUOUS_REPO`.** The maker could not pick one project from your current directory. `NO_REPO` carries `searched_from`. `AMBIGUOUS_REPO` carries `candidates`. Rerun with `--repo-root <absolute path of the main checkout>`.
8. **`NOT_FOUND`, `IDENTITY_MISMATCH`.** `locate`, `verify` or `remove` found no workspace with that identity or path for this project, or `verify` was given a `--kind` or `--slug` that differs from the workspace's marker. Run `list` to see the real entries.
9. **`UNSAVED_WORK`.** See Step 6. Push the work, or rerun `remove` with `--discard`.
10. **`TICKET_NOT_FOUND`.** The `--ticket` path is outside the project, or the ticket file does not exist in the workspace (it is not on `origin/main`). Land the ticket on the hub's `main`, then run `ensure` again. A workspace made for the failed request stays in place.
11. **`BAD_ARGUMENT`.** A missing or invalid flag, a slug that names no work identity, `--ticket` with `--kind scratch`, or `locate` given none of `--path`, `--branch`, or `--kind` with `--slug`. The message names it.
12. **`CLONE_FAILED`, `CHECKOUT_FAILED`, `COPY_FAILED`, `REMOTE_DELETE_FAILED`, `REMOVE_FAILED`.** A git or file operation failed. The message carries the tail of git's error. Fix the named cause (disk space, permissions, hub access), then retry the same command.
13. **`INTERNAL_ERROR`.** The maker met a condition it could not classify. The message names it. Report it with the full answer.

## See Also

- [ADR-070: single workspace maker and resolver](../architecture/adrs/ADR-070-single-workspace-maker-and-resolver.md) — the decision this tool implements.
- [Worktree Manager component](../architecture/components/worktree-manager.md) — where the maker sits in the architecture.
- [Documentation Index](../INDEX.md) — navigation entry point.
