---
title: "Reference: Workspace Maker Interface"
description: "Verbs, flags, JSON answer shape, marker file fields, status codes, exit codes, readiness checks and deploy entry of the one workspace maker (worktree.py); consult it when calling the maker or parsing its answer."
type: reference
status: active
created: 2026-10-14
last_updated: 2026-10-14
components:
  - worktree_manager
  - build_orchestration
related_docs:
  - docs/reference/workspace-maker-answers-and-codes.md
  - docs/architecture/adrs/ADR-070-single-workspace-maker-and-resolver.md
  - docs/architecture/components/worktree-manager.md
---

# Workspace Maker Interface

Lookup tables for the command-line interface of the one workspace maker, `worktree.py`, and for the modules it imports. Every fact comes from the code; the source function for each table is named in its lead line.

---

## Locations

`<install>` below is the project's install folder, `<project>/.leafcutter/`.

| Item | Source path | Deployed path |
|---|---|---|
| Maker entry point (CLI) | `templates/scripts/worktree.py` | `<install>/scripts/worktree.py`, i.e. `<project>/.leafcutter/scripts/worktree.py` |
| Package marker | `templates/scripts/workspace/__init__.py` | `<install>/scripts/workspace/__init__.py` |
| Project-root resolver | `templates/scripts/workspace/workspace_root.py` | `<install>/scripts/workspace/workspace_root.py` |
| Shared primitives | `templates/scripts/workspace/workspace_core.py` | `<install>/scripts/workspace/workspace_core.py` |
| Readiness checks and canary | `templates/scripts/workspace/workspace_checks.py` | `<install>/scripts/workspace/workspace_checks.py` |
| Creation sequence | `templates/scripts/workspace/workspace_create.py` | `<install>/scripts/workspace/workspace_create.py` |

Invocation: `python <absolute path to worktree.py> <verb> [flags]`, from any working directory. The maker is stdlib-only, never reads stdin and never prompts. Constants: `MAKER_VERSION` = `"1.0.0"`, `SCHEMA_VERSION` = `1`, landing folder name `worktrees`, marker file name `.leafcutter-workspace.json`.

---

## Verbs

Source: `worktree.py` `_build_parser`, `verb_*` functions. Every verb except `where` accepts `--repo-root`; a flag marked "required" makes the parser answer `BAD_ARGUMENT` when absent.

| Verb | Creates or changes state | Purpose |
|---|---|---|
| `ensure` | Yes | Make the workspace for one piece of work, or re-verify it when it already exists and is `ready`. The only creating verb. |
| `locate` | No | Find one workspace by path, branch, or kind plus slug. |
| `list` | No | List every workspace marker in the landing place that belongs to the project. |
| `verify` | No (see Known behaviour) | Re-check one workspace's readiness. |
| `remove` | Yes | Delete one workspace folder. |
| `where` | No | Print the maker's own absolute path. |

### ensure

| Flag | Type | Required | Default | Description |
|---|---|---|---|---|
| `--kind` | enum: `ticket`, `feature`, `ac`, `fastlane`, `epic`, `scratch` | Yes | — | Kind of work; selects branch prefix and folder name (see Work Identity). |
| `--slug` | string | Yes | — | Raw work identity; normalised by the maker. |
| `--ticket` | path | No | none | Ticket in the main checkout (absolute, or relative to the project root). Adds `ticket_path_in_worktree` and `ticket_path_in_worktree_posix` to the answer. Refused with `--kind scratch`. |
| `--repo-root` | path | No | resolved from the working directory | Project root; see Project Resolution. |
| `--config-path` | path | No | derived from the main install config | Explicit build config file. Must exist. |
| `--allow-stale-base` | flag | No | off | Accept the existing `origin/main` when the hub is unreachable; also exempts `base_is_fresh` from the readiness requirement on creation. |

Creation sequence (`workspace_create.create_workspace`), in order: clone, base fetch and checkout, copy `.env` and `.mcp.json`, run the workspace's own install build, require readiness, write marker `ready`. A failure at any step deletes the half-made workspace and re-raises.

| Step | Function | Effect |
|---|---|---|
| 1 | `_clone` | `git clone --local --no-checkout <project> <workspace>`; `origin` re-pointed at the hub; `/.leafcutter-workspace.json` and `/.leafcutter-canary-known-bad.py` appended to `.git/info/exclude`; marker written with state `creating`. |
| 2 | `_checkout` | `git fetch origin main`; base = `refs/remotes/origin/main`; checks out the branch (resumes `origin/<branch>` when the hub has it, else branches from base with `--no-track`; `scratch` is detached at base); sets `gc.auto` = `0` and `maintenance.auto` = `false`. |
| 3 | `_copy_env_files` | Copies `.env` and `.mcp.json` from the project when present. |
| 4 | `_build` | Runs `<python> <workspace>/<entry> --target-dir <workspace> --config-path <config>` with a 1800 s timeout. |
| 5 | `require_ready` | Recomputes every check; raises `NOT_READY` on any check that is not `true`. |
| 6 | `write_marker` | Rewrites the marker with state `ready` and the base commit. |

An existing workspace is never rebuilt: `ensure` re-runs `require_ready` (stale base tolerated) and answers.

Build derivation (`derive_build`): without `--config-path`, the main checkout's config is read from `.claude/skills_config.json`, else `.leafcutter/config/skills_config.json`; every `top_level_packages` path prefix is stripped and a copy is written to `<workspace>/.git/workspace_build_config.json`. The build entry is the first existing of `scripts/build.py` and `<package>/scripts/build.py`.

### locate

| Flag | Type | Required | Default | Description |
|---|---|---|---|---|
| `--path` | path | One selector required | — | Workspace folder. Highest precedence. |
| `--branch` | string | One selector required | — | Exact branch recorded in the marker. Used when `--path` is absent. |
| `--kind` with `--slug` | enum, string | One selector required | — | Matches the folder name computed from kind and normalised slug. Used last. |
| `--repo-root` | path | No | resolved | Project root. |

### list

| Flag | Type | Required | Default | Description |
|---|---|---|---|---|
| `--repo-root` | path | No | resolved | Project root. |

`list` scans folders of `<project parent>/worktrees/` whose marker `project_root` equals the project; it never calls `git worktree list`. Order: sorted by folder name.

### verify

| Flag | Type | Required | Default | Description |
|---|---|---|---|---|
| `--path` | path | Yes | — | Workspace folder; must be in the landing place. |
| `--kind` | enum | No | none | When given, must equal the marker `kind`, else `IDENTITY_MISMATCH`. |
| `--slug` | string | No | none | When given, its normalised form must equal the marker `slug`, else `IDENTITY_MISMATCH`. |
| `--repo-root` | path | No | resolved | Project root. |

The stale-base check is tolerated for `verify`.

### remove

| Flag | Type | Required | Default | Description |
|---|---|---|---|---|
| `--path` | path | Yes | — | Workspace folder; must be in the landing place. |
| `--discard` | flag | No | off | Up-front authorisation to delete uncommitted or unpushed work. |
| `--delete-remote-branch` | flag | No | off | Runs `git push origin --delete <branch>` before deletion (skipped when the marker has no branch). |
| `--repo-root` | path | No | resolved | Project root. |

Without `--discard`, `remove` refuses when `git status --porcelain` is non-empty, or when commits exist beyond `origin/<branch>` (when that ref exists) or beyond `origin/main`.

### where

No flags. Answers with `maker_path`, the real path of `worktree.py`.

---

## Work Identity and Naming

Source: `workspace_core.py` (`_PREFIX`, `_ALIASES`, `normalize_slug`, `branch_for`, `dirname_for`, `make_plan`).

| Kind | Branch | Landing folder name for slug `S` |
|---|---|---|
| `ticket` | `ticket/S` | `ticket-S` |
| `feature` | `feature/S` | `feature-S` |
| `ac` | `ac/S` | `ac-S` |
| `fastlane` | `fastlane/S` | `fastlane-S` |
| `epic` | `EPIC-S` | `EPIC-S` |
| `scratch` | none (detached at base) | `scratch-S` |

| Normalisation rule | Behaviour |
|---|---|
| Alias strip | For kind `epic`, a leading `EPIC-` (case-insensitive) is removed. |
| Character class | Runs of characters outside `A-Za-z0-9._-` become `-`. |
| Dots | Runs of two or more `.` collapse to one; leading and trailing `-` and `.` are trimmed. |
| `.lock` suffix | A trailing `.lock` is removed. |
| Empty result | `BAD_ARGUMENT`. |

The workspace path is `<project parent>/worktrees/<folder name>`.

---

## Project Resolution

Source: `workspace_root.py` `resolve_project_root(cwd, repo_root)`. The only public function; recomputed on every call, never cached.

| Order | `how` value | Rule |
|---|---|---|
| 1 | `argument` | `repo_root` given and holds its own `.git`: ok. Given but not a repo: `NO_REPO` immediately. |
| 2 | `workspace-marker` | A `.leafcutter-workspace.json` found walking up from `cwd`; its `project_root` must be a repo root. |
| 3 | `git-common-dir` | `git rev-parse --git-common-dir` of `cwd`, when it ends in `.git`. |
| 4 | `child-search` | Repository folders directly inside `cwd`. |
| 5 | `sibling-search` | Repository folders directly inside `cwd`'s parent. |

Search excludes hidden folders and the `worktrees` folder. One candidate is ok; several give `AMBIGUOUS_REPO`; none gives `NO_REPO`.

| Result key | Type | Present when |
|---|---|---|
| `status` | string: `ok`, `NO_REPO`, `AMBIGUOUS_REPO` | Always. |
| `project_root` | absolute path | `ok`. |
| `how` | string | `ok`, and `AMBIGUOUS_REPO`. |
| `candidates` | list of absolute paths | `AMBIGUOUS_REPO`. |
| `searched_from` | absolute path | `NO_REPO`. |

---

## JSON Answer Shape

> See [workspace-maker-answers-and-codes.md](workspace-maker-answers-and-codes.md) for full details.

---

## Marker File

Source: `workspace_core.write_marker`, `read_marker`; `workspace_create._clone`. File `.leafcutter-workspace.json` at the workspace root, JSON with 2-space indent. Written atomically (temp file `.leafcutter-workspace.json.tmp`, then `os.replace`). Excluded from git through `.git/info/exclude`; it is the maker's registry of workspaces.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | integer | `1`. |
| `kind` | string | One of the six kinds. |
| `slug` | string | Normalised work identity. |
| `branch` | string or null | Line of work; null for `scratch`. |
| `hub` | string | Hub URL. |
| `project_root` | string | Absolute path of the main checkout; the only way a workspace identifies its project. |
| `base_commit` | string | Empty string while `creating`; hub `main` tip once `ready`. |
| `maker_version` | string | Maker version that wrote the record. |
| `state` | string: `creating`, `ready` | `creating` immediately after the clone exists; `ready` is the last creation step. |
| `created_at` | string | UTC ISO-8601 timestamp, second precision. |

---

## Readiness Checks

Source: `workspace_checks.checks_for`, `require_ready`, `canary`, `hook_stages`. Returned as `checks` on `ensure` and `verify`; every value is recomputed from the workspace on disk.

| Check key | True when |
|---|---|
| `is_independent_repo` | `.git` is a real directory (not a symlink), the git common dir is that directory, no `objects/info/alternates` file exists, and `origin` equals the hub. |
| `not_main_checkout` | The workspace real path differs from the project real path. |
| `same_project` | Resolving the project from the workspace gives the recorded project root. |
| `branch_matches` | The checked-out branch (`symbolic-ref --short HEAD`) equals the marker branch (a detached `scratch` HEAD matches null). |
| `not_protected_branch` | The branch is not `main` or `master`. |
| `base_is_fresh` | The hub's current `main` tip (`ls-remote origin refs/heads/main`) equals `base_commit`. Exempted from `require_ready` when stale is tolerated. |
| `build_ok` | `<workspace>/.leafcutter` is a directory. |
| `tree_clean` | `git status --porcelain` is empty. |
| `precommit_config_present` | `.pre-commit-config.yaml` is a file and not a symlink. |
| `hooks_<stage>_fired` | `.git/hooks/<stage>` exists as a file. One key per stage, `-` replaced by `_` (for example `hooks_pre_commit_fired`). Stages: `pre-commit` plus every name in `default_install_hook_types` of the workspace's `.pre-commit-config.yaml` (inline list or block list); `pre-commit` alone when the file is absent. This key tests for the hook file only. |
| `hooks_canary_rejected` | A commit of the known-bad file `.leafcutter-canary-known-bad.py` is rejected, and a control commit with `--no-verify` succeeds. Only the `pre-commit` stage is exercised. |

Canary rules: it is not run (key `false`) when `tree_clean` is false or HEAD does not exist; it stages with `git add -f`; commits run with the working directory set and a fixed identity (`leafcutter-canary`); its own commits are undone with `reset --soft`; the key is `true` only when HEAD afterwards equals its starting value.

`require_ready` raises `NOT_READY` when any check other than the exempted one is not `true`, listing the failing keys in `message`.

---

## Status and Refusal Codes

> See [workspace-maker-answers-and-codes.md](workspace-maker-answers-and-codes.md) for full details.

---

## Exit Codes

> See [workspace-maker-answers-and-codes.md](workspace-maker-answers-and-codes.md) for full details.

---

## Deploy Entry

Source: `scripts/build_phases_script_deploy.py` `WORKSPACE_MAKER_SCRIPTS`; consumed by `build_template_standalone_scripts` and mirrored in `scripts/build_deploy_manifest_helpers.py` (imports the same tuple, adding `scripts/<name>` to the deployed set and `templates/scripts/<name>` to the source set).

| Entry in `WORKSPACE_MAKER_SCRIPTS` | Deployed to |
|---|---|
| `worktree.py` | `<install>/scripts/worktree.py` |
| `workspace/__init__.py` | `<install>/scripts/workspace/__init__.py` |
| `workspace/workspace_root.py` | `<install>/scripts/workspace/workspace_root.py` |
| `workspace/workspace_core.py` | `<install>/scripts/workspace/workspace_core.py` |
| `workspace/workspace_checks.py` | `<install>/scripts/workspace/workspace_checks.py` |
| `workspace/workspace_create.py` | `<install>/scripts/workspace/workspace_create.py` |

| Behaviour | Rule |
|---|---|
| Missing source | A named entry whose source file is absent is recorded through `record_deploy_failure("build_template_standalone_scripts", ...)`. |
| Nested entries | Entries containing `/` are copied explicitly; the shallow `templates/scripts/*.py` glob does not reach them. |
| Overwrite | Compare-before-write; unchanged files are counted as up to date. |

---

## Known Behaviour

Behaviours recorded by the code and its decision history, stated without interpretation.

| Behaviour | Detail |
|---|---|
| Dirty workspace reads not ready | `tree_clean` false forces `hooks_canary_rejected` false, so `ensure` or `verify` of a ready workspace holding uncommitted work answers `NOT_READY`. |
| `verify` runs the canary | On a clean tree it makes and soft-resets canary commits, leaving reflog entries. |
| Hook-stage keys test file presence only | Only `pre-commit` has a canary. |
| Interrupted creation | A process killed mid-`ensure` can leave a `creating` workspace; `ensure` then answers `WORKSPACE_INCOMPLETE` until `remove --path <workspace> --discard`. |
| No symlinks | The maker and the build it drives make none. |

---

## See Also

- [ADR-070: single workspace maker and resolver](../architecture/adrs/ADR-070-single-workspace-maker-and-resolver.md) — decision context for one maker, the separate resolver, and the named deploy entries.
- [Worktree manager component](../architecture/components/worktree-manager.md) — architecture of the workspace lifecycle component that owns this surface.
- `templates/scripts/worktree.py` — verbs and CLI.
- `templates/scripts/workspace/workspace_root.py` — project resolver.
- `templates/scripts/workspace/workspace_core.py` — naming, marker, scan primitives.
- `templates/scripts/workspace/workspace_checks.py` — readiness checks and canary.
- `templates/scripts/workspace/workspace_create.py` — creation sequence.
- `scripts/build_phases_script_deploy.py` — `WORKSPACE_MAKER_SCRIPTS`.
