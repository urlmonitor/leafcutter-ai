---
title: "Reference: Shared Commit Step"
description: "Lookup for calling the shared commit step (commit_changes.py): its inputs, every key of its one JSON answer, the four statuses and what a caller does next, the reason_code families, the rules a caller can rely on, the remedy and handoff payload, and one real answer per status."
type: reference
status: active
created: 2026-10-16
last_updated: 2026-10-16
components:
  - build_orchestration
  - git_vcs_operations
  - documentation_system
related_docs:
  - docs/architecture/agent_delivery_workflows.md
  - docs/architecture/components/build-orchestration.md
  - docs/reference/remedy-declarations.md
  - docs/acceptance-criteria/build-orchestration/BO-4500-fix-once-every-route/BO-4500a-4-vi.yaml
---

# Shared Commit Step

Lets the author of a route, on any orchestration framework, look up how to call `commit_changes.py`, what it accepts, and how to read and act on the one JSON answer it prints. Any caller that can start a process in the workspace and read its standard output can use it.

---

## Invocation

```bash
python <scripts>/commit_changes.py --message-file FILE [--supervised (--run ID | --ac-id ID)] PATH [PATH ...]
```

| Property | Value |
|---|---|
| Working directory | The workspace (any directory inside the git work tree to commit in). |
| Standard output | Exactly one JSON object followed by a newline; nothing else is written there. |
| Exit code | `0` for `committed` and `nothing_to_commit`; `1` for `refused` and `hook_failed`. `--help` prints the usage text and exits `0`. |
| Standard error | Diagnostics only (for example an index-sync warning); a caller parses standard output, not standard error. |

---

## Inputs

| Input | Type | Required | Description |
|---|---|---|---|
| `PATH` (one or more) | repo file | Yes | An explicit file to commit, relative to the working directory or absolute. Only explicit files are accepted: a directory, a glob (`*`, `?`, `[`), a pathspec starting with `:`, or an `all` request is refused (`policy_path_not_a_file`). A path outside the workspace is refused (`policy_path_outside_workspace`); a path that neither exists nor is tracked is refused (`policy_path_not_found`). One bad entry refuses the whole call before anything is staged. A deleted tracked file may be named so the deletion is committed. |
| `--message-file FILE` | file path | Yes | File holding the commit message. Also accepted as `--message-file=FILE`. A missing option, a missing file, an unreadable file or a whitespace-only file is refused. |
| `--supervised` | flag | No | Marks a call made on behalf of a run with no person present. Checks get no terminal input, and a check silent for `input_wait_limit_seconds` is ended. Never inferred from the environment. |
| `--run ID` | free text | One of `--run` / `--ac-id` when supervised | The run the call commits for. Echoed unchanged in the answer's `run`. |
| `--ac-id ID` | free text | One of `--run` / `--ac-id` when supervised | The acceptance criterion the call commits for. Echoed unchanged in the answer's `ac_id`. |
| `--` | marker | No | Everything after it is a `PATH`, even when it starts with `-`. |

`--run` and `--ac-id` may also be passed without `--supervised`; they are echoed the same way. Any other option is refused (`policy_unknown_option`). A supervised call naming neither is refused (`policy_unattributed_supervised_call`) before anything is staged.

---

## Answer Keys

Every answer carries every key below, in this order, at its empty value unless the status fills it. The keys and empty values are read from `config/commit_step.json` (`answer_keys`).

| Key | Type | Empty value | Meaning |
|---|---|---|---|
| `status` | string | `null` | One of `committed`, `nothing_to_commit`, `refused`, `hook_failed`. |
| `reason_code` | string | `null` | Machine-readable code from the vocabulary below; `null` only on `committed`. |
| `reason` | string | `null` | Human-readable explanation of the code. |
| `sha` | string | `null` | Full sha of the new commit. |
| `paths` | list of strings | `[]` | Repo-relative files the commit carries, sorted: the named files that changed plus `added_parents`. |
| `added_parents` | list of strings | `[]` | Structural parent AC records the step added because a named AC record's parent was edited. |
| `unlisted_changes` | list of strings | `[]` | Files a check staged that the caller did not name; they were dropped from the commit. |
| `autofixed` | list of objects | `[]` | One `{hook_name, files}` entry per run in which a fixing check rewrote files and the checks were re-run. |
| `hook_name` | string | `null` | The failing check, when the output names one. |
| `failing_files` | list of strings | `[]` | Carried files named in the failing check's output. |
| `hook_output` | string | `null` | The check's output, verbatim. |
| `remedy` | object | `null` | The `remedy` member of `handoff`; see [Remedy and Handoff](#remedy-and-handoff). |
| `handoff` | object | `null` | The handoff payload; `null` unless the failing check declares a specialist. |
| `skip_request_ignored` | list of strings | `[]` | Environment requests to skip checks that the step dropped. |
| `run` | string | `null` | The `--run` value, echoed. |
| `ac_id` | string | `null` | The `--ac-id` value, echoed. |
| `answer_version` | integer | `null` | Contract version; `1` at present. |

A refusal made before the request was understood (for example `step_config_unreadable`) cannot read the key list and then carries only `status`, `reason_code`, `reason`, `sha`, `paths`, `hook_name` and `failing_files`.

---

## Statuses

| Status | Meaning | Filled keys | Caller does next |
|---|---|---|---|
| `committed` | The commit was recorded. | `status`, `sha`, `paths`, `answer_version`; `added_parents`, `unlisted_changes`, `autofixed`, `skip_request_ignored` when non-empty; `run`/`ac_id` when passed. `reason_code` and `reason` stay `null`. | Record `sha`. Read `unlisted_changes`: those files are still modified in the work tree and were not committed. Read `autofixed` and `skip_request_ignored` for information. |
| `nothing_to_commit` | The named files have no change against `HEAD`. | `status`, `reason_code` (`nothing_changed`), `reason`, `answer_version`. | Do not treat this as success where work was expected: investigate why the named files are unchanged. No commit exists. |
| `refused` | The step declined or could not finish; nothing was committed. | `status`, `reason_code`, `reason`, `answer_version`; `run`/`ac_id` when passed. | Act per the family of `reason_code`; see the next section. |
| `hook_failed` | A check failed; nothing was committed. | `status`, `reason_code`, `reason`, `hook_output`, `hook_name` and `failing_files` when the output names them, `remedy` and `handoff` when the check declares a specialist, `answer_version`. | Act on `remedy.disposition` when present; otherwise the author clears the check's complaint and calls again. |

---

## Reason Codes

The enumeration is read from `config/commit_step.json` (`reason_codes`). A `refused` answer carries a `policy` or `step` code, a `hook_failed` answer a `check` code, a `nothing_to_commit` answer a `nothing` code, and a `committed` answer none. The step refuses to emit a code outside its status's families.

### policy (status `refused`)

Caller rule: stop; do not retry unchanged; fix the request.

| Code | Raised when |
|---|---|
| `policy_no_explicit_paths` | No `PATH` was given. |
| `policy_path_not_a_file` | An entry is a directory, a glob, a `:` pathspec or an `all` request. |
| `policy_path_outside_workspace` | An entry resolves outside the workspace. |
| `policy_path_not_found` | An entry does not exist and is not tracked. |
| `policy_message_missing` | `--message-file` was not given. |
| `policy_message_not_found` | The message file does not exist. |
| `policy_message_unreadable` | The message file cannot be read. |
| `policy_message_empty` | The message file holds only whitespace. |
| `policy_protected_branch` | The current branch is `main`, `master` or origin's default branch. |
| `policy_detached_head` | The workspace is on no branch. |
| `policy_unattributed_supervised_call` | `--supervised` without `--run` or `--ac-id`. |
| `policy_unknown_option` | An option the step does not accept. |

### step (status `refused`)

Caller rule: the step could not finish. The caller may retry the identical call up to `max_transient_retries` (config, default `3`) times, then stop and report. The step itself never retries a step failure.

| Code | Raised when |
|---|---|
| `step_index_locked` | Another process holds the shared index lock; nothing was staged or committed, and the lock is left untouched. |
| `step_vcs_error` | A git operation failed, git could not run, or the step hit an unexpected error. |
| `step_config_unreadable` | `config/commit_step.json` is missing or invalid. There is no fallback vocabulary; the step refuses. |
| `step_parent_resolver_unavailable` | AC records were named but the resolver that finds their parents is not deployed beside the script. |

### check (status `hook_failed`)

Caller rule: act on `remedy.disposition` when `remedy` is non-null; when `remedy` is `null`, the author clears the complaint in `hook_output` and calls again.

| Code | Raised when |
|---|---|
| `check_failed` | A check that judges rather than fixes failed. Reported at once with the check's output verbatim; never retried. |
| `check_unsettled` | A fixing check was still rewriting files on the last allowed run (`max_automated_fix_retries`). |
| `check_awaited_input` | A supervised call's check was silent for `input_wait_limit_seconds` and was ended. `hook_name` names the check when the output identified it. |

### nothing (status `nothing_to_commit`)

| Code | Raised when |
|---|---|
| `nothing_changed` | None of the named files differs from `HEAD`. Caller rule: never read as a success where work was expected. |

### Extending the vocabulary

The vocabulary is config-driven. Adding a code or an answer key is a config edit and is additive. Renaming or removing a code, or moving a code to another family, is breaking and needs `answer_version` to change. The shape of the file is `config/commit_step.schema.json`.

| Config key | Value | Meaning |
|---|---|---|
| `answer_version` | `1` | Version of the answer contract. |
| `max_automated_fix_retries` | `3` | Re-runs of the checks after a fixing check's rewrite. |
| `max_transient_retries` | `3` | Retries a caller may make of a `step_*` refusal. |
| `input_wait_limit_seconds` | `60` | Silence after which a supervised check is ended. |

---

## Rules a Caller Can Rely On

| Rule | Guarantee |
|---|---|
| Only named files are committed | The commit is `HEAD` plus the named files, built in a private index; other callers' staged work in the shared index is neither read nor reset. |
| Structural parents | When a named record is an AC record whose parent was edited, that parent is added and listed in `added_parents`. |
| Unlisted files are dropped | A file a check stages that was not named (or added as a parent) is removed from the new commit and reported in `unlisted_changes`. |
| Message lands verbatim | The message file's text is committed unchanged (`--cleanup=verbatim`). |
| Checks always run | The repository's commit checks run on every call. `SKIP` and `PRE_COMMIT_ALLOW_NO_CONFIG` are dropped from the environment and a `core.hooksPath` injected through the environment is dropped; each is named in `skip_request_ignored`. A `core.hooksPath` in the repository's own config is honoured. |
| Fixing checks | A check that rewrites a carried file has the rewrite taken into the commit and the checks re-run, up to `max_automated_fix_retries` (config, default `3`) times; each is recorded in `autofixed`. A still-rewriting check ends as `check_unsettled`. |
| Judging checks | A check that fails without rewriting a carried file is reported at once as `hook_failed` / `check_failed`; it is never retried. |
| Protected branches | `main`, `master`, the default branch origin's locally recorded `HEAD` names, and a detached checkout are refused (`policy_protected_branch`, `policy_detached_head`). The comparison is by whole branch name and reads no network state. |
| Config required | Missing or invalid config is `refused` / `step_config_unreadable`; there is no built-in fallback. |
| Index lock | A held shared index lock is `refused` / `step_index_locked`. |
| Supervised | Checks receive no terminal input. A check producing no output for `input_wait_limit_seconds` is ended with its process group, nothing is committed, and the answer is `hook_failed` / `check_awaited_input`. |
| Refusals are answers | Every refusal, and any unexpected failure, is one JSON answer with exit `1`; no traceback or partial JSON reaches standard output. |

---

## Remedy and Handoff

When a failing check declares an `engage-specialist` remedy, `remedy_handoff.py` builds one payload and the step returns it as `handoff`, with its `remedy` member copied to `remedy`. A check with no such declaration leaves both `null`. The declarations are described in [Remedy Declarations](remedy-declarations.md).

| Field | Type | Meaning |
|---|---|---|
| `status` | string | Always `handoff`. |
| `handoff_target` | string | The specialist the declaration names. |
| `record_handoff_target` | string | The same name, for the caller's record. |
| `flips_signed_off` | boolean | Always `false`; a handoff does not complete the work. |
| `message` | string | One-line statement of the refusal and who is needed. |
| `remedy.hook_id` | string | The refusing check. |
| `remedy.disposition` | string | What happens next; `engage-specialist` here. |
| `remedy.skills` | list of strings | Skills the specialist loads. |
| `remedy.demand` | list | The check's `*REFUSAL_RECORD:` list, verbatim and in refusal order. |

Captured by running `remedy_handoff.py --hook-id check-complexity` on a hand-written refusal file holding a `COMPLEXITY_REFUSAL_RECORD:` line:

```json
{
  "status": "handoff",
  "handoff_target": "restructuring-specialist",
  "record_handoff_target": "restructuring-specialist",
  "flips_signed_off": false,
  "message": "check-complexity refused the commit; restructuring-specialist is needed to meet the demand, then the commit is re-offered unchanged.",
  "remedy": {
    "hook_id": "check-complexity",
    "disposition": "engage-specialist",
    "skills": ["complexity-reduction"],
    "demand": [
      {"path": "src/app.py", "function": "load", "score": 14, "ceiling": 10, "reason": "complexity 14 exceeds 10"}
    ]
  }
}
```

### Layering

| Party | Does |
|---|---|
| The step | Answers. It never spawns or engages anyone. |
| The commit agent | Relays the answer, including `remedy` and `handoff`, unchanged. |
| The depth-0 caller | On an `engage-specialist` handoff, engages the named specialist at most once, then re-offers the identical path list and message file. |

---

## Example Answers

Each answer below is real output of the built step, run with `env -C <scratch-repo> python templates/scripts/commit_changes.py --message-file /tmp/cs_demo_msg.txt <PATH>` in a scratch repository on branch `work`, with the key order and values as printed and only the line breaks added. The `committed` and `nothing_to_commit` answers come from one repository, `notes.txt` being committed and then named again; `hook_failed` comes from a second repository whose `.git/hooks/pre-commit` prints a line and exits `1`; `refused` is the same call naming `.`. The sha is as captured.

### committed

Call: `... notes.txt`

```json
{"status": "committed", "reason_code": null, "reason": null,
 "sha": "12549f64887f53a183c517af7a5a2df01f3c7de8",
 "paths": ["notes.txt"], "added_parents": [], "unlisted_changes": [], "autofixed": [],
 "hook_name": null, "failing_files": [], "hook_output": null, "remedy": null, "handoff": null,
 "skip_request_ignored": [], "run": null, "ac_id": null, "answer_version": 1}
```

### nothing_to_commit

Call: `... notes.txt` again, exit `0`.

```json
{"status": "nothing_to_commit", "reason_code": "nothing_changed",
 "reason": "named paths have no changes", "sha": null,
 "paths": [], "added_parents": [], "unlisted_changes": [], "autofixed": [],
 "hook_name": null, "failing_files": [], "hook_output": null, "remedy": null, "handoff": null,
 "skip_request_ignored": [], "run": null, "ac_id": null, "answer_version": 1}
```

### refused

Call: `... .`, exit `1`.

```json
{"status": "refused", "reason_code": "policy_path_not_a_file",
 "reason": "cannot commit these entries: . (policy_path_not_a_file)", "sha": null,
 "paths": [], "added_parents": [], "unlisted_changes": [], "autofixed": [],
 "hook_name": null, "failing_files": [], "hook_output": null, "remedy": null, "handoff": null,
 "skip_request_ignored": [], "run": null, "ac_id": null, "answer_version": 1}
```

### hook_failed

Call: `... notes.txt` against the failing hook, exit `1`. The hook's output does not name the check in the `<name>....Failed` form, so `hook_name` is `null`; the author clears the complaint in `hook_output`.

```json
{"status": "hook_failed", "reason_code": "check_failed",
 "reason": "demo-check: notes.txt must not contain the word first", "sha": null,
 "paths": [], "added_parents": [], "unlisted_changes": [], "autofixed": [],
 "hook_name": null, "failing_files": ["notes.txt"],
 "hook_output": "demo-check: notes.txt must not contain the word first\n",
 "remedy": null, "handoff": null,
 "skip_request_ignored": [], "run": null, "ac_id": null, "answer_version": 1}
```

---

## See Also

- [Agent Delivery Workflows](../architecture/agent_delivery_workflows.md) — where routes reach the commit phase.
- [Build Orchestration](../architecture/components/build-orchestration.md) — the component that owns the shared commit step.
- [Remedy Declarations](remedy-declarations.md) — how a check declares the remedy a handoff carries.
- `config/commit_step.json` — the vocabulary: answer keys, reason codes, retry ceilings and the wait limit.
- `config/commit_step.schema.json` — the shape of that file.
- `templates/scripts/commit_changes.py` — the step.
- `templates/scripts/commit_guardian/remedy_handoff.py` — builds the handoff payload.
