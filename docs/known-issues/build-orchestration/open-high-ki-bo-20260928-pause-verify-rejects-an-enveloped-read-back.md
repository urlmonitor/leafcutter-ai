---
title: "KI-BO-20260928-pause-verify-rejects-an-enveloped-read-back — plan-feature reports pause_persist_failed (\"CANNOT be resumed\") for a pause record that was written and read back, because the verify only accepts `exists` at the top level of the reply and worktree-agent wrapped it"
description: "high — pauseAtGate checks `_verified.exists === true` on the parsed reply (plan-feature.js:1891). In run wf_a2fd1222-f54 worktree-agent returned {\"pause_record\": {\"exists\": true, ...}, \"worktree\": {...}}, so a written, verified record was reported unresumable. Resuming with args.resume_answer worked. Three other pause-store reads use the same top-level check."
type: reference
category: reference
status: active
created: '2026-09-28'
last_updated: '2026-09-28'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260927-status-checker-runs-workflow-shell-commands.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260901-1620.md
  - docs/how-to/resume-a-paused-plan-feature-run.md
---

# KI-BO-20260928-pause-verify-rejects-an-enveloped-read-back — plan-feature reports pause_persist_failed ("CANNOT be resumed") for a pause record that was written and read back, because the verify only accepts `exists` at the top level of the reply and worktree-agent wrapped it

- **Severity:** high. The run tells the user it cannot be resumed when it can. A user who believes
  that message re-runs `/plan-feature` from the start or drives the agents by hand, and the
  record that was written is left behind in `paused_runs/`.
- **Status:** open. No AC. Traced to code.
- **Occurrences:** 1 (`/plan-feature` run `wf_a2fd1222-f54`, run id
  `plan-ki-cg-20260831-0713-20260927`, gate `gate-ba`, 2026-09-27)
- **First seen:** 2026-09-27 · **Last seen:** 2026-09-27
- **Where:** `templates/workflows-js/plan-feature.js:1882-1891` (`pauseAtGate()`'s read-back
  verify) and the failure return at `:1896-1909`. The same top-level check is at `:1619`
  (`peek-pause-record`), `:1703` (`read-pause-record`) and `:1773` (`clear-pause-record-verify`).
  The deployed `.claude/workflows/plan-feature.js` differs from the template only in comments.

## Symptom

The `pause-persist` dispatch returned (fenced) `{"ok": true, "idempotent": false, "path":
"...\\.leafcutter\\paused_runs\\plan-ki-cg-20260831-0713-20260927.json"}`. The
`pause-persist-verify` dispatch then returned, inside a ```` ```json ```` fence:

```json
{
  "pause_record": {
    "exists": true,
    "stale": false,
    "record": { "run_id": "plan-ki-cg-20260831-0713-20260927", "gate_id": "gate-ba", "...": "..." }
  },
  "worktree": { "status": "created", "worktree_path": "C:\\Users\\..." }
}
```

The run still ended with `status: "pause_persist_failed"` and the message "the pause record
... could not be verified as written, so this run CANNOT be resumed". Re-invoking the workflow
with `args.resume_answer` for `gate-ba` worked: the resume's own `peek-pause-record` and
`read-pause-record` read-backs were accepted, and the run continued to the BA stage commit.

## Mechanism

1. The verify prompt asks for `EXACTLY its stdout JSON of the form
   {"exists":<bool>,"stale":<bool>,"record":<obj|null>}` (`:1885`). No `schema:` is passed to
   `agent()` (`:1886`; `plan-feature.js` passes a `schema:` nowhere), so nothing enforces that
   shape. The reply shape is whatever the agent decides.
2. The fences are not the problem. `parseAgentJson()` (`:121`) scans for the first balanced
   `{...}` and parses it, so it returned the whole outer object.
3. `_persistVerified = !!(_verified && _verified.exists === true)` (`:1891`). The outer object's
   keys are `pause_record` and `worktree`. `exists` is one level down, so the check reads
   `undefined` and the verify fails.
4. `:1896-1909` then returns `pause_persist_failed` with the "CANNOT be resumed" message. The
   write's own `{"ok": true}` reply is discarded (`:1865` does not keep the result), so the
   workflow has no second signal to weigh against the failed read-back.

**Why worktree-agent wraps.** The pause-store calls were moved to `worktree-agent` by PR #896
because `status-checker` refused them (see
`KI-BO-20260927-status-checker-runs-workflow-shell-commands`). `worktree-agent`'s template makes
it a worktree lifecycle agent with "exactly two actions: create and remove"
(`templates/agents/worktree-agent.md:85`). Its Machine-Parsed Dispatch Output Contract
(`:207-240`) shows a payload built around `worktree_path` and `status`. In this run it answered
in that frame: it put the requested stdout under a key of its own and added a `worktree` status
block. These dispatches ran on a Haiku model. Whether a given reply is wrapped depends on the
wording and the model, so the failure is intermittent.

**The same check at three more sites.** Each reads `exists` at the top level only:

| line | site | effect of a wrapped reply |
|---|---|---|
| `:1619` | `peek-pause-record` | returns `null`: no paused gate found |
| `:1703` | `read-pause-record` | returns `nothing_to_resume`, so the resume is refused |
| `:1773` | `clear-pause-record-verify` (checks `exists === false`) | the clear is reported as failed and a stale record is left |

Only the verify site has been observed. The other three are the same parse and are exposed in
the same way.

## Detection

A `pause_persist_failed` result whose `pause-persist` step returned `"ok": true`. Check
`<repo>/.leafcutter/paused_runs/<run_id>.json`: if it exists and names the gate, the pause is
resumable. `python "$REPO_ROOT/.leafcutter/scripts/pause_store.py" --store-dir
"$REPO_ROOT/.leafcutter/paused_runs" read --run-id <run_id>` prints the unwrapped
`{"exists": true, ...}` (step 2 of `docs/how-to/resume-a-paused-plan-feature-run.md`).

## Workaround

Ignore the "CANNOT be resumed" message when the record file exists. Re-invoke the workflow with
`resumeFromRunId` set to the run's `run_id` and `args.resume_answer` for the named gate, as in
`docs/how-to/resume-a-paused-plan-feature-run.md`.

## Fix direction

1. Pass a `schema:` for `{exists, stale, record}` on all four pause-store read dispatches, so the
   harness rejects or retries a wrapped reply instead of the workflow misreading it.
2. Failing that, accept one level of wrapping when exactly one nested object carries `exists`,
   `stale` and `record`. Do not search deeper: a lenient search could read an `exists` out of the
   record's own context.
3. Keep the write's reply. When the write said `ok: true` and only the read-back failed, report
   "unverified, check `<path>`" and name the path, rather than "CANNOT be resumed".
4. The durable fix is the one both status-checker KIs name: a shell-executor agent chartered to run
   one given command and return its stdout, with no output contract of its own to fold the reply
   into (`KI-BO-20260901-1620` item 4).

**Pattern:** a strict verify made loose at the input end. The check is exact, the reply shape is
not enforced, and the agent chosen to produce the reply has its own output contract.
