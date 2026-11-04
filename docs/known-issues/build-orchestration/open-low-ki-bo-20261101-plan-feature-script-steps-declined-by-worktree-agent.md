---
title: "KI-BO-20261101-plan-feature-script-steps-declined-by-worktree-agent — /plan-feature sends its pause-store and stage-script steps to worktree-agent, which declines them on its two-action charter; a declined rule check is read as a failed check, forces a BA re-run, and the run aborts with the approved drafts uncommitted"
description: "medium — plan-feature.js hard-codes worktree-agent for the pause-store reads and clear (:1579, :1654, :1704) and for every stage-end script step (scriptStepAgentId, :2202). worktree-agent's charter is 'exactly two actions: create and remove' (worktree-agent.md:71), so it declines at random. On 2026-10-30 (run wf_4a8567df-505) it declined peek-pause-record (retry worked), clear-pause-record and the third rule-check-ba. runRuleCheck() turns the decline into 'no readable report (JSON Parse error: Unexpected EOF)' (:2020), the gate forces edit (:2917), and the stage aborts 'business-analyst failed to produce satisfactory ACs after 2 attempts' (:2941). Every dispatch in the run went to the same agent type; the earlier ones complied."
type: reference
category: reference
status: active
created: '2026-11-01'
last_updated: '2026-11-04'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20261022-pause-persist-failed-at-gate-ba-in-a-maker-workspace.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260927-status-checker-runs-workflow-shell-commands.md
  - docs/known-issues/build-orchestration/open-low-ki-bo-20261101-shell-reply-schema-admits-a-wrapped-reply.md
  - docs/known-issues/ac-driven-dev/open-high-ki-acd-20261022-rule-check-resolves-the-store-root-against-the-session-cwd.md
  - docs/how-to/resume-a-paused-plan-feature-run.md
---

# KI-BO-20261101-plan-feature-script-steps-declined-by-worktree-agent — /plan-feature sends its pause-store and stage-script steps to worktree-agent, which declines them on its charter, and a declined rule check aborts the stage as a BA failure

> Filed 2026-11-01. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** medium. Nothing is lost on disk: the drafts stay in the workspace and can be
  committed by hand. But the run's own answer is wrong. It blames the business-analyst for a
  step the BA never ran, re-runs the BA on drafts the user had approved, and then aborts with
  those approved drafts uncommitted. A stale pause record is left behind as well.
- **Status:** open. No AC. The fix is already ticketed for the stage-script steps:
  `tickets/00_inbox/TICKET-20261021-PlanFeatureScriptStepsToShellRunner.md` (status `todo`). That
  ticket does not cover the pause-store reads and clear (`:1579`, `:1654`).
- **Occurrences:** 2 (`/plan-feature` run `wf_4a8567df-505`, run id `default-run`, workspace
  `ac/tq-200d-before-score-fixes`, BA stage, 2026-10-29 to 2026-10-30; run `wf_6207f8a0-8ee`,
  run id `pf-entry-pause-20261104`, BA stage, 2026-11-04)
- **First seen:** 2026-10-30 · **Last seen:** 2026-11-04
- **Where** (`templates/workflows-js/plan-feature.js` at base `d62440669`; the deployed
  `.claude/workflows/plan-feature.js` is the same body with the shared block inlined):
  - `:1579` — `readPauseRecordWithRetry()` dispatches every pause-record read with
    `agentType: "worktree-agent"` (labels `peek-pause-record`, `read-pause-record`,
    `clear-pause-record-verify`, `pause-persist-verify`).
  - `:1654` — `resolveGate()` sets `_shellPermittedAgentId = "worktree-agent"`; `:1704` sends
    `clear-pause-record` to it. `:1758` does the same in `pauseAtGate()`.
  - `:2198` — `workspaceSetupAgentId = (args && args.workspace_setup_agent) || "shell-runner"`.
    Only the workspace-setup step reads `args.workspace_setup_agent`.
  - `:2199-2202` — `scriptStepAgentId = "worktree-agent"`, with the comment that these steps
    "stay on worktree-agent until the follow-up ticket ... rewrites them for shell-runner
    (ADR-070)". Used by `runRuleCheck()` (`:1999-2022`) at `:2864`, `:2915`, `:3041`, and by the
    design, approval-hold, approval-apply and hand-back steps (`:2805`, `:2978-2979`, `:3080`).
  - The charter: `templates/agents/worktree-agent.md:71` — "You have exactly two actions:
    **create** and **remove**."

## Symptom

After the user approved gate `gate-ba` (resume on 2026-10-30), the run returned:

> business-analyst failed to produce satisfactory ACs after 2 attempts. Pipeline aborted.
> Pipeline cancelled at max-retries abort for business-analyst. Uncommitted draft AC files ...

The 11 drafts (TQ-200d-5 and its children, TQ-200d-1-ii, TQ-200d-2-i/-ii, TQ-200d-4-i..iv) were
left uncommitted. They were committed by hand afterwards as `dd053b3fa`.
`.leafcutter/paused_runs/default-run.json` (written 2026-10-29 20:09) is still in the workspace.

## What the journal shows

From `wf_4a8567df-505/journal.jsonl` and each agent's `.meta.json`. Every pause-store and
rule-check dispatch in the run went to `agentType: "worktree-agent"`. The agent type did not
change between the dispatches that worked and the ones that were declined.

| # | label | agent | when (UTC) | reply |
|---|---|---|---|---|
| 15 | `rule-check-ba` | worktree-agent | 10-29 20:08 | ran the command (exit 1, verdict `failed`, see below) |
| 17 | `pause-persist` | worktree-agent | 10-29 20:09 | `{"ok": true, ...}` |
| 19 | `pause-persist-verify` | worktree-agent | 10-29 20:09 | `{"exists": true, ...}` |
| 21 | `peek-pause-record` | worktree-agent | 10-29 | `{"exists": true, ...}` |
| 25 | `peek-pause-record` | worktree-agent | 10-30 07:32 | declined: "I did not run this read. Reading the pause record is not one of the two actions this agent handles (`create` and `remove`)" |
| 27 | `peek-pause-record-retry-1` | worktree-agent | 10-30 07:32 | `{"exists": true, ...}` |
| 29 | `read-pause-record` | worktree-agent | 10-30 07:32 | `{"exists": true, ...}` |
| 31 | `clear-pause-record` | worktree-agent | 10-30 07:33 | declined: "My role is limited to the two workspace actions, create and remove, and clearing a paused run's durable record is neither." |
| 33 | `rule-check-ba` | worktree-agent | 10-30 07:33 | ran the command (exit 1, verdict `failed`, see below) |
| 35 | `stage-ba-author` | business-analyst | 10-30 07:33 | re-ran the BA |
| 37 | `rule-check-ba` | worktree-agent | 10-30 07:34 | declined: `{"output": "", "exit_code": null, "stderr": "NOT_RUN: the worktree-agent only performs the create and remove workspace actions. ..."}` |

The two rule checks that did run (#15, #33) did not pass either. Both reported
`records_checked: 0` and "store root ... is outside the repository". The store root resolved to
the session's cwd: `C:\Users\Hendrik\Code\leafcutter` on 10-29 and
`...\leafcutter-ai-worktrees\fastlane\tq-500f-2-ii` on 10-30. That is
`KI-ACD-20261022-rule-check-resolves-the-store-root-against-the-session-cwd`, recorded there as an
occurrence. So the brief's "the pre-gate rule check succeeded" holds for the dispatch, not for the
check: worktree-agent ran it, and the check failed for another reason.

## Mechanism

1. **Routing.** None of these steps can be routed elsewhere. `readPauseRecordWithRetry()` and the
   clear hard-code `"worktree-agent"` (`:1579`, `:1654`). The stage-script steps use
   `scriptStepAgentId` (`:2202`), a constant. `args.workspace_setup_agent` (`:2198`) reaches only
   the workspace-setup step, and `shell-runner` is used only for the shared workspace-answer steps
   (`read-workspace-marker`, `detect-current-branch`).
2. **The charter says no.** worktree-agent has two actions (`worktree-agent.md:71`). Reading,
   clearing, or running a rule check is neither, so whether a prompt is run depends on the model's
   reading of its charter. In this run it ran 7 of 10 such dispatches and declined 3. The same
   decline caused `KI-BO-20261022-pause-persist-failed-at-gate-ba-in-a-maker-workspace` (occurrence
   2) on the pause-store write.
3. **A decline reads as a failed check.** `runRuleCheck()` does `JSON.parse(reply.output)`
   (`:2013`). The declined reply's `output` is `""`, so it throws, and the catch returns
   `failed("the check produced no readable report (JSON Parse error: Unexpected EOF)")` (`:2020`).
   Nothing tells "the agent would not run it" apart from "the check failed".
4. **A failed check forces an edit, and the edit budget is 1.** After the gate, `:2915` runs the
   check again (the resume path skipped it), and `:2917` turns any non-passing check into
   `action = "edit"`. Check #33 failed (store root), so `reapprove = true` and the BA re-ran
   (#35). Check #37 was declined, so the gate was auto-approved (`:2867`, `reapprove &&
   !ruleCheck.passed`), the check failed again at `:2917`, and with `MAX_EDIT_RETRIES = 1` (`:54`)
   the stage aborted at `:2936-2945` naming the business-analyst.
5. **The clear's decline is only a log line.** At `:1720-1728` a clear that is not verified sets
   `_clearVerifyFailed` and logs a warning, then the run continues. That is why the pause record
   is still on disk.

## Detection

- A `failed to produce satisfactory ACs` abort, or a gate summary saying `Rule check failed: the
  check produced no readable report`. Open the run's `journal.jsonl` and find the `rule-check-*`
  result. A `NOT_RUN` / "only performs the create and remove" reply is this issue.
- Any `peek-pause-record`, `read-pause-record` or `clear-pause-record` result in prose that
  mentions "create and remove".
- `ls <workspace>/.leafcutter/paused_runs/` still lists a run that has moved past its gate.

## Workaround

Used on 2026-10-30 and it worked: run the rule check by hand with absolute paths (see the
store-root KI), commit the stage output from the main loop as `plan-feature(BA): <component>`
with `AC IDs:` and `run-id:` lines, and start a new run. Delete the stale
`paused_runs/<run_id>.json` once nothing is waiting on it.

## Fix direction

1. Do the ticket: rewrite each script step as one plain command and send it to `shell-runner`
   (`TICKET-20261021-PlanFeatureScriptStepsToShellRunner`). Extend its scope to the pause-store
   reads and clear (`:1579`, `:1654`, `:1704`, `:1758`), which the ticket does not name.
2. Read every script-step reply with the shared `shellStepReply()`
   (`templates/workflows-js/_shared/workspace-answer.js:70-92`), which already tells a decline
   (`kind: "declined"`) from a result. Treat a decline as a routing failure: halt with "the agent
   declined <step>" and keep the drafts. Never send it into the edit loop.
3. Do not spend the author's edit budget on a check that did not run. Only a check that ran and
   reported findings should become BA feedback.

**Pattern:** a step sent to an agent whose charter forbids it, with a reply reader that cannot
tell "refused" from "failed". The refusal is then blamed on the next agent in line.

## Occurrence 2026-11-04 — rule-check-ba declined; the check itself also failed

On run `wf_6207f8a0-8ee` (run id `pf-entry-pause-20261104`), `rule-check-ba` went to
`worktree-agent`, which replied `{"output": "", "exit_code": null, "stderr": "NOT_RUN:
requirement_rule_check.py is outside the worktree-agent's two actions (create and remove)."}`.
The gate summary then read "Rule check failed: the check produced no readable report (JSON Parse
error: Unexpected EOF)". In the run just before it (`wf_59d7a401-0f3`), `read-covering-ac-titles` and the first
`pause-persist-verify` were declined the same way.

The main session ran the same command by hand, from the workspace. It ran (`records_checked:
14`) and returned `verdict: failed`, with 25 findings needing a decision. They were contract
symmetry (a child's `expects_from` with no `delivers_to` on the producer, an IT-PO field) and
stale `test_intent` clause texts on the parent records ACD-1300e-3 and ACD-1300e-4, which the BA
had touched only to add `covered_by` links. So the post-gate re-check at `:2915` would have
sent the BA back to edit, for findings that belong to the IT-PO stage or to records it only
linked. The person approved gate-ba, and the stage was committed
from the main loop (`927934e33`).
