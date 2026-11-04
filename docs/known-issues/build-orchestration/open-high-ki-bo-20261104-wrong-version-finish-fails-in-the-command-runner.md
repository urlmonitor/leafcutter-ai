---
title: "KI-BO-20261104-wrong-version-finish-fails-in-the-command-runner — the fast lane sends the wrong-version finish step to command-step-runner as one long heredoc command, and the runner failed it three different ways in three runs, each time after the code was done"
description: "high — fast-lane-ship.js (:1767-1772) builds `wrong_version_gate.py finish --reply - ... <<'WV_REPLY_EOF'` with test-breaker's whole reply inlined and dispatches it to command-step-runner (:1735-1743). On 2026-11-04 it halted 3 of the 5 lane runs that reached it: wf_39ec449a-05e lost the backslashes of an unquoted Windows path (exit 2, can't open file); wf_c8675472-b9c ran past the runner's 120 s foreground timeout, was moved to background and came back with no exit status; wf_8a32dad7-55f was declined because a safety monitor read the prepared wrong versions, which by design disable scorer checks, as 'Security Test Removal'. Each time the gate passed when run by hand with the same reply."
type: reference
category: reference
status: active
created: '2026-11-04'
last_updated: '2026-11-04'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20261021-unquoted-shell-args.md
  - docs/known-issues/build-orchestration/open-low-ki-bo-20261023-gate-verdicts-sensitive-to-machine-load.md
  - docs/known-issues/build-orchestration/open-low-ki-bo-20261101-shell-reply-schema-admits-a-wrapped-reply.md
---

# KI-BO-20261104-wrong-version-finish-fails-in-the-command-runner — the wrong-version finish step fails in its runner, not in its gate

> Filed 2026-11-04. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`high`); the original grading is the
> `**Severity:**` line below.

- **Severity:** high. It halted 3 of the 5 fast-lane runs that reached the step on 2026-11-04.
  Every halt came after the code and tests were finished and green, so the whole run was lost and
  the claims released. Nothing wrong was committed: the step parses fail-closed. But a correct
  change cannot ship through the lane on these runs, and the halt message (`unparseable reply` or
  a script error) points at the gate, which worked.
- **Status:** open. No AC.
- **Occurrences:** 3, all on 2026-11-04, while building the TQ-200d re-run fix ACs:
  - `wf_39ec449a-05e` (`TQ-200d-2-iii`): backslashes lost from the path.
  - `wf_c8675472-b9c` (`TQ-200d-5-iv`): foreground timeout, no exit status.
  - `wf_8a32dad7-55f` (`TQ-200d-1-iv`): runner declined on safety grounds.
- **First seen:** 2026-11-04 · **Last seen:** 2026-11-04
- **Where** (`templates/workflows-js/fast-lane-ship.js` at `origin/main` `72ddec43f`):
  - `:1728-1730` — `wvDir`, `wvIds`, `wvFlags`: the worktree path and AC-store path pasted in
    unquoted.
  - `:1735-1743` — `wvStep()`: sends `{step, command, target}` to `command-step-runner`
    (`CLAIM_EXECUTOR_AGENT_TYPE`, `:1062`) with `CLAIM_RUNNER_SCHEMA` (`:1073`), then takes the
    last JSON line of `reply.stdout`, or returns `unparseable reply`.
  - `:1758-1764` — test-breaker's whole reply becomes `wvReply`.
  - `:1767-1772` — the finish command:
    `python ${wvDir}/wrong_version_gate.py finish --work-key ${targetAc} --reply - ${wvIds}${wvFlags} <<'WV_REPLY_EOF'`,
    then `wvReply` inline, then the delimiter. Any reply that is not `gate_passed: true` halts via
    `wvHalt()` (`:1744`).
  - `templates/agents/command-step-runner.md` — the runner's charter. It says nothing about a
    timeout or about long-running commands.

## Symptom

The three runs failed differently, but the pattern was the same. The finish step halted the lane
with `failing_phase: wrong-version`, `wrong_version_step: finish`. Then
`wrong_version_gate.py finish` was run by hand in the same workspace with the same reply, and it
exited 0 with a normal verdict.

**a. Backslashes lost (`wf_39ec449a-05e`, `TQ-200d-2-iii`).** The worktree path reached the shell
as a Windows path with backslashes. It is pasted in unquoted, so the shell read each `\` as an
escape and dropped it. A path of the form `C:\<a>\<b>\<c>\...` came out as
`C:<a><b><c>...`, one run-together string. Python reported `can't open file` and exited 2.
stdout had no JSON line, so `wvStep()` returned `unparseable reply` and the lane halted.

**b. Timeout (`wf_c8675472-b9c`, `TQ-200d-5-iv`).** `finish` runs every owed wrong version against
its tests, so it can take minutes. It ran past the runner's 120 s foreground Bash limit, and the
runner's tool moved it to the background. The runner replied before the command ended, with no
exit status and no verdict line. `wvStep()` returned `unparseable reply`.

**c. Safety decline (`wf_8a32dad7-55f`, `TQ-200d-1-iv`).** The heredoc carries test-breaker's
prepared wrong versions. By design these are replacements that disable or weaken the checks the
scorer makes, so the guarding tests can be shown to catch them. A safety monitor read the command
as "Security Test Removal" and the runner declined to run it. The decline has no `stdout`, so
`wvStep()` returned `unparseable reply` again. (It never calls `classifyStepReply()`, so the decline
is not reported as one.)

## Mechanism

1. **One command carries all the data.** The step puts the whole test-breaker reply inside the
   shell line as a heredoc. The command is long, contains code edits that look like test
   sabotage when read out of context, and is passed through an LLM agent that must reproduce it
   exactly in its own Bash call.
2. **The runner is literal and has the agent's own limits.** `command-step-runner` runs the string
   as given. That is right for its role, but it means three things. Unquoted paths break on
   backslashes and spaces (see `KI-BO-20261021-unquoted-shell-args`). A slow command meets the
   Bash tool's foreground timeout. And the content is screened by the same safety layer as any
   other agent action.
3. **The reader cannot tell these apart.** `wvStep()` reduces every failure, including a decline,
   a backgrounded command and a script that never started, to `unparseable reply`. The halt
   detail does not say which part failed.

## Why this is one entry, and how it relates to others

All three failures are in how the command reaches the shell, not in the gate. They share one fix
(do not pass a large, slow, data-carrying command through an agent's Bash call), so one entry.

- (a) is the first live occurrence of `KI-BO-20261021-unquoted-shell-args`, which was found by
  reading the code. An occurrence is recorded there too. That entry's fix (quote every path)
  would have stopped (a), but not (b) or (c).
- (b) has the same shape as `KI-BO-20261023-gate-verdicts-sensitive-to-machine-load` (a slow
  step whose result depends on timing), but there the gate's verdict changed; here no verdict came
  back at all.
- `KI-BO-20261101-shell-reply-schema-admits-a-wrapped-reply` is about a reply shape that the schema
  allows. `CLAIM_RUNNER_SCHEMA` has the same gap (no `required`), but no reply here was wrapped.

## Detection

A halt with `failing_phase: wrong-version`, `wrong_version_step: finish` and
`wrong_version_detail.error` starting `unparseable reply:`. Look at the quoted reply:

- `exit_status: 2` and stderr `can't open file` with a path that has lost its separators: (a).
- No `exit_status`, or text about a background task: (b).
- `declined: true`, or prose about a test removal: (c).

Then confirm it is this entry: run the same `finish` command by hand in the workspace, with the
reply written to a file. A normal verdict means the gate was fine.

## Workaround

Run `wrong_version_gate.py finish` by hand in the workspace with the reply from a file, check the
verdict, then finish the commit and PR by hand. A rerun of the lane may pass, but it redoes all
the earlier phases.

## Fix direction

1. Write test-breaker's reply to a file in the run's scratch item and pass `--reply <path>`, not
   `--reply -` with a heredoc. The command becomes short and carries no code edits.
2. Quote every path (the `KI-BO-20261021-unquoted-shell-args` fix), or pass paths with forward
   slashes.
3. Run `finish` as a background job with a result file, or set an explicit long timeout on the
   runner's Bash call, and have the reader wait for the result. It must not take a reply that
   has no exit status as the end of the step.
4. In `wvStep()`, call `classifyStepReply()` first, as the other command steps do, so a decline
   is reported as a decline and the halt names the cause.
5. Size ratchet: `fast-lane-ship.js` is over the file-size limit
   (`KI-BO-20260930-fast-lane-ship-is-649-lines-over-and-cannot-grow`). A fix that adds lines
   needs a shrink in the same commit or the user's `check-file-size` skip.

**Pattern:** a deterministic gate that is reached only through an LLM agent's shell call, so the
gate's reliability is limited by the agent's quoting, timeouts and safety screening, none of which
the gate's own tests exercise.
