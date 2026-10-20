---
title: "Reference: the workspace maker's answer"
description: "Every field, status, exit code and outcome code of the answer the workspace maker prints, and the rules a caller must follow when acting on it."
type: reference
status: active
created: 2026-10-13
last_updated: 2026-10-13
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
2. The workspace's location is taken from `workspace_path` of an ok answer only. Never take
   it from an agent's own words or from the folder the caller is in.
3. The answer has the same form whichever route asked: a workflow, the skill, an agent or a
   person at a terminal.

## Channel and common fields

Standard output carries exactly one JSON object; all child-process output goes to standard
error. Every answer has:

| Field | Meaning |
|---|---|
| `status` | `ok`, `refused` or `error` |
| `code` | one of the codes below; `OK` on an ok answer |
| `verb` | the verb that was asked |
| `schema_version` | integer, currently 1; adding a field is compatible, renaming or removing one bumps it |
| `message` | on a non-ok answer, the cause in words |

`workspace_path`, `workspace_path_posix` and `worktree_path` are present on an ok answer
and absent on every non-ok answer.

## Exit codes

| Exit code | Status |
|---|---|
| 0 | `ok` |
| 2 | `refused`: a well-understood precondition failed |
| 1 | `error`: anything else |
| 64 | `error` with code `USAGE` |

## Codes

| Code | Status | Meaning |
|---|---|---|
| `OK` | ok | The request was done. |
| `NOT_FOUND` | refused | No workspace with a marker at that place. |
| `INCOMPLETE` | refused | The workspace is half-made and could not be finished safely. |
| `OCCUPIED` | refused | The place already holds other work; left as it is. |
| `OCCUPIED_LEGACY_WORKTREE` | refused | An old-style worktree occupies the work's place. |
| `IN_PROGRESS` | refused | Another request for the same workspace is running. |
| `NO_REPO` | error | No project was found from where the request ran. |
| `AMBIGUOUS_REPO` | refused | More than one project matches. |
| `NO_HUB` | refused | The project has no `origin` remote to use as the shared project. |
| `FETCH_FAILED` | refused | The latest shared state could not be fetched. |
| `GIT_FAILED` | error | A git step failed. |
| `NO_CONFIG` | refused | The project configuration the workspace needs is missing. |
| `BOOTSTRAP_FAILED` | refused | Installing the workspace's own tools failed. |
| `BOOTSTRAP_DIRTIED_TRACKED` | refused | Installing the tools changed tracked files. |
| `WORK_AT_RISK` | refused | Finishing the workspace in place would endanger work in it. |
| `HOOKS_INACTIVE` | refused | The declared commit protections did not fire in the workspace. |
| `VERIFY_FAILED` | refused | A readiness check failed; see `checks`. |
| `UNSENT_WORK` | refused | `remove` found unpushed commits or uncommitted files. |
| `PROCESS_HOLDS_FILES` | refused | A program holds files, so the folder could not be fully cleared. |
| `ON_PROTECTED_BRANCH` | refused | The workspace is on a protected branch. |
| `TICKET_NOT_ON_BASE` | refused | The named ticket file is not on the shared project's base. |
| `AMBIGUOUS_LINE` | refused | More than one line of work exists on the shared project for this work; the answer lists the `lines`. Name one. |
| `USAGE` | error | The arguments were unusable (exit 64). |
| `INTERNAL_ERROR` | error | The maker failed unexpectedly; never an ok answer. |
| `REFUSED` | refused | Legacy generic refusal of a dirty or unpushed remove. |

## Fields by verb

| Verb | Extra fields on ok |
|---|---|
| `ensure` | `workspace_action` (`created`, `re-readied`, ...), `kind`, `slug`, `branch`, `line_of_work`, `hub`, `base_commit`, `bootstrap`, `hooks_stages_declared`, `checks`, `repo_root`, `layout`; with `--ticket`, `ticket_path_in_worktree` |
| `locate` | `marker` (kind, slug, branch, state, base_commit, checks, ...) |
| `list` | `landing_place`, `workspaces` (each with its `workspace_path` and `marker`) |
| `remove` | what was cleared and, if authorised, the discarded set |
| `where` | `path`, the maker script's own location |
| `verify` | the readiness `checks` for one workspace |

## Discard token

On an `UNSENT_WORK` refusal of `remove`, the answer carries `unsent` (`commits` and `files`)
and `discard_token`. Repeat the request with `--discard-token <token>` to discard. The token
is one-time, bound to that workspace and exactly the listed unsent set, valid only on the
`remove` request for that workspace while the set is unchanged. It is never an environment
variable or config setting and is never remembered.
