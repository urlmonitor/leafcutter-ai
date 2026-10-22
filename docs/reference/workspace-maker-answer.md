---
title: "Reference: the workspace maker's answer"
description: "Every field, status, exit code and outcome code of the answer the workspace maker prints, and the rules a caller must follow when acting on it."
type: reference
status: active
created: 2026-10-13
last_updated: 2026-10-22
components:
  - worktree_manager
  - build_orchestration
related_docs:
  - docs/how-to/get-a-workspace.md
  - docs/how-to/clear-a-workspace.md
  - docs/architecture/components/worktree-manager.md
  - docs/architecture/diagrams/c3-034-workspace-request-halt-sequence.md
  - docs/architecture/diagrams/c3-031-workspace-request-states.md
---

# Reference: the workspace maker's answer

The authoritative contract is acceptance criterion `BO-4300c-2`; the code table lives in
`templates/scripts/worktree_answer.py`. This page is the lookup form. If they disagree, the
contract wins. For procedures see [Get a workspace](../how-to/get-a-workspace.md) and
[Clear a workspace](../how-to/clear-a-workspace.md).

## Caller rules

1. Anything other than `"status": "ok"` means the caller stops. No working step runs.
   Callers treat `refused` and `error` alike.
2. The workspace's location is taken from `workspace_path` of an ok answer only. Never take
   it from an agent's own words or from the folder the caller is in.
3. The answer has the same form whichever route asked: a workflow, the skill, an agent or a
   person at a terminal.

## Channel and common fields

Standard output carries exactly one JSON object (UTF-8, no byte-order mark, at most one
trailing newline). All child-process output (git, package installers, the build) goes to
standard error. The maker never reads standard input and never prompts. Every answer has:

| Field | Meaning |
|---|---|
| `schema_version` | integer, currently 1; adding a field is compatible, renaming or removing one bumps it |
| `status` | `ok`, `refused` or `error` |
| `code` | one of the codes below; `OK` on an ok answer |
| `message` | one sentence naming the cause |
| `verb` | the verb that was asked |
| `repo_root`, `repo_root_posix` | the project's main checkout, native and POSIX spelling |
| `layout` | `dev` or `consumer` |
| `mechanism` | `clone` |
| `hub` | the main checkout's `origin` URL |

`workspace_path`, `workspace_path_posix` and `worktree_path` are present on an ok answer
and absent on every non-ok answer: not blank, not null. Diagnostic paths on a non-ok answer
travel under other names (see [Fields on a non-ok answer](#fields-on-a-non-ok-answer)).

## Exit codes

| Exit code | Status |
|---|---|
| 0 | `ok` |
| 2 | `refused`: a well-understood precondition failed |
| 1 | `error`: anything else |
| 64 | `error` with code `USAGE`; still one JSON object |

## Codes

These are all the codes. No answer carries a generic `REFUSED` code.

| Code | Status | Meaning |
|---|---|---|
| `OK` | ok | The request was done. |
| `NOT_FOUND` | refused | No workspace with a marker at that place. |
| `INCOMPLETE` | refused | The workspace is half-made and could not be finished safely; see `remnant_path`. |
| `OCCUPIED` | refused | The place already holds other work; left as it is. See `occupant`. |
| `OCCUPIED_LEGACY_WORKTREE` | refused | An old-style worktree occupies the work's place. See `occupant`. |
| `IN_PROGRESS` | refused | Another request for the same workspace is running. |
| `NO_REPO` | error | No project was found from where the request ran; see `searched_from`. |
| `AMBIGUOUS_REPO` | refused | More than one project matches; see `candidates`. |
| `NO_HUB` | refused | The project has no `origin` remote to use as the shared project. |
| `FETCH_FAILED` | refused | The latest shared state could not be fetched. |
| `GIT_FAILED` | error | A git step failed; see `step`. |
| `NO_CONFIG` | refused | The project configuration the workspace needs is missing. |
| `BOOTSTRAP_FAILED` | refused | Installing the workspace's own tools failed. |
| `BOOTSTRAP_DIRTIED_TRACKED` | refused | Installing the tools changed tracked files. |
| `WORK_AT_RISK` | refused | Finishing the workspace in place would endanger work in it; see `unsent`. |
| `HOOKS_INACTIVE` | refused | The declared commit protections did not fire in the workspace; see `inactive_stages`. |
| `VERIFY_FAILED` | refused | A readiness check failed; the answer names the `failed_ingredients` and carries the `checks`. |
| `UNSENT_WORK` | refused | `remove` found unpushed commits or uncommitted files; see `unsent` and `discard_token`. |
| `PROCESS_HOLDS_FILES` | refused | Programs hold files, so the folder could not be cleared; see `holders`. |
| `ON_PROTECTED_BRANCH` | refused | The workspace is on a protected branch, or `remove --delete-remote-branch` names a protected branch of the shared project. |
| `TICKET_NOT_ON_BASE` | refused | The named ticket file is not on the shared project's base; see `ticket_path` and `reason`. |
| `AMBIGUOUS_LINE` | refused | More than one line of work exists on the shared project for this work; the answer lists the `lines`. Name one. |
| `BUILT_FOR_OTHER_TICKET` | refused | `ensure --kind ticket` for a line already recorded as built for a different ticket; the answer names `branch`, `recorded_ticket` and `ticket_path`. Nothing was written; ask with a different slug. |
| `USAGE` | error | The arguments were unusable (exit 64). This includes a `--slug` that is empty after normalising, is a Windows reserved device name (`con`, `nul`, `com1`, ...), or is longer than 64 characters (never truncated). |
| `INTERNAL_ERROR` | error | The maker failed unexpectedly; never an ok answer. |

## Fields on an ok answer

### ensure, locate and verify

| Field | Meaning |
|---|---|
| `kind`, `slug` | the work's identity |
| `branch` | the line of work; null for `scratch` |
| `workspace_path`, `workspace_path_posix` | the workspace, absolute, native and POSIX spelling |
| `worktree_path` | alias, always equal to `workspace_path` |
| `base_ref` | `origin/main` |
| `base_commit` | the commit read back from the workspace |
| `origin_main_commit` | the commit of `origin/main` at the fetch |
| `base_matches_origin_main` | true when `base_commit` equals `origin_main_commit` |
| `fetch` | `ok`, `failed` or `skipped` |
| `workspace_action` | `created`, `re-readied`, `completed` or `located` |
| `line_of_work` | `new`, `resumed` or `existing` |
| `created` | true when this request made the workspace |
| `checks` | the readiness checks, each `true`, `false` or `n/a` (see [Checks](#checks)) |
| `ticket_path_in_worktree`, `ticket_path_in_worktree_posix` | only when the request named `--ticket`: the ticket inside the workspace, verified to exist; absent on every other answer |

Only `ensure` adds:

| Field | Meaning |
|---|---|
| `bootstrap` | `{build_ok, config_path, restored_tracked, env_copied, failure_excerpt}`: whether the build passed, the install config used, the repo-relative tracked files the build changed and the maker restored, the names of the environment files copied in, and an excerpt of the build failure (null when none) |
| `hooks_stages_declared` | the hook stages the project declares |

For `ensure --kind ticket --ticket`, the workspace's config also records the ticket as
`branch.<branch>.leafcutterTicket` (its project-relative path), which finalization reads.

`locate` and `verify` neither fetch nor build. They answer `workspace_action` `located`,
`line_of_work` `existing`, `created` false and `fetch` `skipped`. Their
`origin_main_commit` is the workspace's last-fetched `origin/main` (null when it has none),
and `base_matches_origin_main` compares `base_commit` with that value. They carry no
`bootstrap` and no `hooks_stages_declared`. They also add `marker`: the workspace's own
marker record (kind, slug, branch, state, base commit, recorded checks).

The located fields are given only for a ready workspace. When the marker is not ready, the
answer is `INCOMPLETE` (with `remnant_path`), and every located field is absent.

`locate --branch` that matches two workspaces by alias answers `AMBIGUOUS_LINE` (refused),
listing them in `candidates`.

`verify` never fetches, builds or commits. It refuses with `VERIFY_FAILED`, a protected branch
included (`not_protected_branch` in `failed_ingredients`), on a false structural check, on `build_ok` false, on a recorded
hook-stage result that is false, or on an identity mismatch. It never refuses on
`base_is_fresh` or `tree_clean`; those are reported in `checks` only.

`ticket_path_final` and `ticket_path_new` are never emitted.

### Checks

| Check | Meaning |
|---|---|
| `is_independent_repo` | the workspace is its own repository |
| `not_main_checkout` | the workspace is not the main checkout |
| `same_project` | the workspace belongs to this project |
| `origin_matches_hub` | the workspace's `origin` is the hub; a trailing `/`, a `.git` suffix and `file://` versus a plain local path do not count as differences; never `n/a` |
| `gc_auto_disabled` | automatic garbage collection is off (`gc.auto` is 0); never `n/a` |
| `install_paths_regular` | the installed paths are regular files and folders (BO-4300b-4); never `n/a` |
| `branch_matches` | the workspace is on its line of work |
| `not_protected_branch` | the workspace is not on a protected branch |
| `base_is_fresh` | the base is the shared project's current `origin/main` |
| `build_ok` | the workspace's build passed; on `locate` and `verify` it is `null` when the workspace's record holds no build result, and only `false` is refused |
| `tree_clean` | no changes to tracked files; untracked files never count. The same on `ensure`, `locate` and `verify` |
| `precommit_config_present` | the workspace has a pre-commit config |
| `hooks_pre_commit_fired`, `hooks_commit_msg_fired`, `hooks_post_merge_fired` | each hook stage fired |
| `hooks_canary_rejected` | the conjunction of the three stage checks: every declared stage fired |

The `n/a` rule for the stage checks: for kind `scratch`, all three and the conjunction are
`n/a`. For any other kind, `hooks_pre_commit_fired` is never `n/a`, and the commit-msg and
post-merge checks are `n/a` only when the project does not declare that stage.

### list, remove and where

| Verb | Extra fields on ok |
|---|---|
| `list` | `workspaces`: one entry per workspace, `{kind, slug, branch, workspace_path, workspace_path_posix, state}`, with `state` `ready` or `incomplete` |
| `remove` | `removed_path` and `discarded` (`{commits, files}`, empty unless a discard was authorised) |
| `where` | `path`, the maker script's own location |

## Fields on a non-ok answer

| Field | On | Meaning |
|---|---|---|
| `step` | any non-ok answer from a failed child-process step | a short name of the step, such as `fetch origin main`; the step's own output is on standard error only, never in `message` or `step` |
| `inactive_stages` | `HOOKS_INACTIVE` | the declared stages that did not fire |
| `ticket_path`, `reason` | `TICKET_NOT_ON_BASE` | the path as requested; `absent` or `differs` |
| `candidates` | `AMBIGUOUS_REPO`; `AMBIGUOUS_LINE` from `locate --branch` | the matching project paths; or the workspaces the branch matched by alias |
| `searched_from` | `NO_REPO` | where the search started |
| `occupant` | `OCCUPIED`, `OCCUPIED_LEGACY_WORKTREE` | `{path, kind, branch}`; `kind` is `other-line`, `other-project`, `plain-folder` or `legacy-worktree`; `branch` may be null |
| `remnant_path` | `INCOMPLETE` | the half-made workspace |
| `unsent` | `UNSENT_WORK`, `WORK_AT_RISK` | `{commits, files}` |
| `discard_token` | `UNSENT_WORK` on `remove` only | see [Discard token](#discard-token) |
| `holders` | `PROCESS_HOLDS_FILES` | `[{pid, name}]`, one entry per program holding files |
| `lines` | `AMBIGUOUS_LINE` | the lines of work that hold this identity |
| `branch`, `recorded_ticket`, `ticket_path` | `BUILT_FOR_OTHER_TICKET` | the line, the repo-relative POSIX ticket path it is recorded as built for, and the path as requested |
| `failed_ingredients`, `checks` | `VERIFY_FAILED` | the names of the false checks, and all the checks; `failed_ingredients` may also hold `identity` when `--kind`/`--slug` differ from the marker's canonical identity |
| `hub_branch_deleted` | `remove --delete-remote-branch` whose local delete failed | true: the branch on the shared project was already deleted |

## Discard token

On an `UNSENT_WORK` refusal of `remove`, the answer carries `unsent` (`commits` and `files`)
and `discard_token`. Repeat the request with `--discard-token <token>` to discard. The token
is one-time, bound to that workspace and exactly the listed unsent set, valid only on the
`remove` request for that workspace while the set is unchanged. It is never an environment
variable or config setting and is never remembered. It never appears on `ensure`'s
`WORK_AT_RISK` or on any other answer.
