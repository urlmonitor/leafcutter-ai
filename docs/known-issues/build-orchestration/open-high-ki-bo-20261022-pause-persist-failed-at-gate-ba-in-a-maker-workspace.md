---
title: "KI-BO-20261022-pause-persist-failed-at-gate-ba-in-a-maker-workspace — /plan-feature returned pause_persist_failed at gate-ba from a workspace-maker workspace because worktree-agent declined the pause-store write, and the code still carries two more ways to produce it"
description: "high — the BA gate's pause record was reported unwritten, so the run could not be resumed. Not filed as an occurrence of KI-BO-20260928 (enveloped read-back) or KI-BO-20260927 (status-checker refusal): the reply was not kept, and pause-store calls no longer go to status-checker. Three candidate paths are open at origin/main 411b87761: an enveloped read-back, a worktree-agent decline, and an unescaped single quote in the --record argument (inferred)."
type: reference
category: reference
status: active
created: '2026-10-25'
last_updated: '2026-10-25'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260928-pause-verify-rejects-an-enveloped-read-back.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260927-status-checker-runs-workflow-shell-commands.md
  - docs/known-issues/ac-driven-dev/open-high-ki-acd-20261022-rule-check-resolves-the-store-root-against-the-session-cwd.md
  - docs/known-issues/ac-driven-dev/open-high-ki-acd-20261022-plan-feature-entry-omits-the-permission-verdict.md
  - docs/how-to/resume-a-paused-plan-feature-run.md
---

# KI-BO-20261022-pause-persist-failed-at-gate-ba-in-a-maker-workspace — /plan-feature returned pause_persist_failed at gate-ba from a workspace-maker workspace because worktree-agent declined the pause-store write, and the code still carries two more ways to produce it

- **Severity:** high. The run could not be resumed. The user has to commit the stage by hand and
  start a new run, and the drafts are at risk if they do not.
- **Status:** open. No AC. **Mechanism established on the second occurrence (2026-10-25):
  `worktree-agent` declined the write (candidate path 2).** See the section at the end. The first
  occurrence's replies were not kept, so it may or may not have had the same cause.
- **Occurrences:** 2 (`/plan-feature` for KM-400d-4-i..iii, 2026-10-22; `/plan-feature` run
  `finalize-gate-child-1`, 2026-10-25; both at gate `gate-ba`, both from a workspace made by
  `.leafcutter/scripts/worktree.py ensure --kind ac`)
- **First seen:** 2026-10-22 · **Last seen:** 2026-10-25
- **Where:** `templates/workflows-js/plan-feature.js:1756-1802` (`pauseAtGate()`): the write prompt
  at `:1778-1782`, the write dispatch at `:1783` (its reply is discarded), the read-back at
  `:1785-1787`, the failure return at `:1788-1801`. The read-back helper is
  `readPauseRecordWithRetry()` (`:1570-1589`).

## Symptom

At the BA gate the run returned `status: "pause_persist_failed"`: the pause record "could not be
verified as written, so this run CANNOT be resumed". No resume was possible.

## What the code rules out

- **Not a status-checker refusal.** Every pause-store call now goes to `worktree-agent`
  (`:1758`, `:1579`). `KI-BO-20260927-status-checker-runs-workflow-shell-commands` covers the
  older status-checker path.
- **Not a missing script.** `buildPauseStoreCommand()` (`:1974-1990`) first `cd`s into the
  workspace. A maker workspace is a clone, so `git rev-parse --git-common-dir` is its own `.git`
  and `$REPO_ROOT` is the workspace. The workspace's install has
  `.leafcutter/scripts/pause_store.py` (checked on this clone).

## Candidate paths still open in the code

1. **Enveloped read-back** (`KI-BO-20260928-pause-verify-rejects-an-enveloped-read-back`). The
   read-back now retries three times (`:1574-1588`), but each attempt still accepts only a reply
   whose top-level `exists` is a boolean (`:1583`), and no `schema:` is passed. A `worktree-agent`
   that wraps its answer every time still yields `null`, so `:1788` fails.
2. **worktree-agent declines.** Its template gives it "exactly two actions: **create** and
   **remove**" (`templates/agents/worktree-agent.md:71`). Writing a pause record is neither. A
   decline on the write leaves no record; the read-back then says `exists: false`.
3. **Inferred: a single quote in the record breaks the shell command.** The write passes the record
   as `--record '` + `JSON.stringify(rec)` + `'` (`:1781`). `JSON.stringify` does not escape `'`. The
   mid-gate context includes the stage's rule-check summary (`:2888`). In this run that summary was
   probably a failure: the same session's rule check was resolving the store root outside the
   workspace (see `KI-ACD-20261022-rule-check-resolves-the-store-root-against-the-session-cwd`). A
   summary built from a JSON parse error message (`:2020`) can contain quotes, for example V8's
   `Unexpected token 'X'`. One `'` ends the quoted argument, the write fails, and the read-back
   finds no record. Not reproduced.

## Detection

A `pause_persist_failed` result. Check `<workspace>/.leafcutter/paused_runs/<run_id>.json`. If it
exists, this is path 1: follow the related KI's workaround and resume. If it does not exist, the
write failed (path 2 or 3). Check whether the gate context's `rule_check` text contains a `'`.

## Workaround

Used on 2026-10-22, and it worked:

1. Show the BA drafts to the user.
2. Commit the BA output from the main loop as `plan-feature(BA): <component>`, with `AC IDs:` and
   `run-id:` lines in the body.
3. Start a NEW run (new `run_id`). It crash-resumes past the committed BA stage.

## Fix direction

1. Keep the write's reply and report it. "Write said X, read-back said Y" tells the next reader
   which path fired.
2. Pass the record through a file or stdin, not a single-quoted shell argument. At minimum, escape
   `'` as `'\''`.
3. Pass a `schema:` on the pause-store reads, and move the pause-store calls to `shell-runner`,
   the agent chartered to run one command and relay it (ADR-070). That closes paths 1 and 2.

**Pattern:** a failure that discards its own evidence. The workflow knew what the write returned
and threw it away, so the report cannot say which of three causes it was.

## Occurrence 2026-10-25 — mechanism established: path 2 (worktree-agent declines)

Reproduced on run `finalize-gate-child-1` (workflow run `wf_1133c2f0-d2d`), `/plan-feature` in a
maker workspace (`ac/finalize-merge-gate-person-only`, base `411b87761`). The BA stage wrote its
drafts, then gate-ba ended `pause_persist_failed`. The workflow's journal kept the reply the
workflow itself discards. The `pause-persist` dispatch to `worktree-agent` returned:

```text
{"status":"error","code":"UNSUPPORTED_ACTION","message":"worktree-agent only supports 'create'
 and 'remove'. The requested task is to persist a pause record for gate 'gate-ba' by running a
 compound shell command that calls pause_store.py. That is neither action, so nothing was run and
 no pause record was written.", ...}
```

`pause-persist-verify` then read `{"exists": false, "stale": false, "record": null}`. So the cause
was candidate path 2: the agent declined on its charter. It also gave a second reason: the command
is a compound shell line (`cd`, `||`, `&&`, subshells), which the global shell rules forbid. Path 1
(wrapped read-back) and path 3 (quote in the record) did not fire in this run.

That settles fix direction 3: move the pause-store dispatches to `shell-runner` (ADR-070) and give
it single commands, not a compound line. Fix direction 1 still stands. The journal was the only
place this reply survived.
