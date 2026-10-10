---
title: "KI-BO-20261009-completion-write-closes-a-ticket-whose-gate-failed — /build-feature wrote status: done on a ticket whose ac-fulfillment-gate had just failed and whose AC was still todo, because the completion decision takes the gate's last entry by file position and a blocker entry was inserted above an older ok"
description: "blocker — phantom-done at the orchestration layer. On 2026-09-30, ticket 02 of EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace was set to status: done while agents.ac-fulfillment-gate read failed and its source AC BO-4300f-4 read work_status: todo. The gate's new blocker entry had been written above its older ok entry (just before a level-2 '## Escalation' heading inside an earlier comment), and completionVerdictFromRecord reads the last entry in file order, so the gate counted as passed. A frontmatter value of failed only adds a phase to the required set; it never makes it outstanding."
type: reference
category: reference
status: active
created: '2026-10-09'
last_updated: '2026-10-09'
components:
  - build_orchestration
  - supervisor_system
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/supervisor-system/open-high-ki-ss-002.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260831-1931.md
  - docs/known-issues/build-orchestration/open-low-ki-bo-20260831-1932.md
  - docs/known-issues/supervisor-system/open-low-ki-ss-20260927-commit-signoff-precedes-the-commit.md
---

# KI-BO-20261009-completion-write-closes-a-ticket-whose-gate-failed — a ticket was recorded done with its gate failed and its AC todo

- **Severity:** blocker. This is the phantom-done failure the package exists to prevent, and it
  happened in the driver's own completion decision. Nothing in the run output says that a failed
  gate was overridden. The ticket simply reads `done`, and `done` releases its dependants.
- **Status:** open, no AC. Mechanism verified by reading `origin/main` `c373b005e` and the ticket's
  committed history. The insertion cause (below) is inferred from the file positions.
- **Occurrences:** 1 (ticket `02_TICKET-20260928-BO-4300-deployed-maker-test-support.md`,
  2026-09-30, the run between commits `08d190daf` (22:50 UTC) and `45e6f2268` (23:06 UTC) on branch
  `epic/every-piece-of-separate-work-gets-its-workspace`).
- **First seen:** 2026-09-30 · **Last seen:** 2026-09-30
- **Where:** `templates/workflows-js/build-feature.js`: `readTicketRecordBack` (:1287-1308, sign-offs
  reported "in the order they appear", :1295); `completionVerdictFromRecord` (:957-1060, the latest
  entry is `entries[entries.length - 1]`, :1035-1036); `demandedPhasesFromRecord` (:1096-1107);
  `concludeTicket` (:1503-1544, writes done when `verdict.completed`, :1521-1522); the cross_agent
  skip (:2469-2475). Also `templates/agents/architect-review.md:254-271` (the `## Escalation` heading).

## Symptom

Commit `08d190daf` reopened ticket 02 (`ac-fulfillment-gate: needed`, `status: in_progress`) after
ticket 04 landed. The next drive ran architect-review (ok) and ac-fulfillment-gate. The gate
returned a blocker: under `AC_ENFORCE_STRICT=1` three `test_bo_4300f_4` tests still failed, so it
left BO-4300f-4 at `work_status: todo`. The drive then set the ticket to `status: done` anyway. The
commit message of `45e6f2268` records the repair: "The drive nevertheless set the ticket to done:
revert that to in_progress".

At that moment the record held:

```text
status: done                          (written by the completion step)
agents.ac-fulfillment-gate: failed
BO-4300f-4.yaml  work_status: todo
```

## Mechanism

1. **The blocker entry landed above the old ok entry.** The ticket's committed copy at `45e6f2268`
   shows the order of the gate's two entries:

   ```text
   358: ### 2026-09-30 10:40 — ac-fulfillment-gate (status: blocker)
   362: ## Escalation
   486: ### 2026-09-28 15:05 — ac-fulfillment-gate (status: ok)
   ```

   In `08d190daf`, line 358 was `## Escalation`. That level-2 heading belongs to architect-review's
   2026-09-28 comment, because `architect-review.md:254-257` tells the agent to "append
   `## Escalation` to your output". The gate's entry went in directly before it. Inferred: the
   writer took the first `## ` heading after `## Comments` as the end of the section.
2. **"Latest" means last in file order.** The read-back lists sign-offs "in the order they appear"
   (:1295), and the verdict takes the last one per agent (:1035). For ac-fulfillment-gate that was
   the 2026-09-28 ok, so the gate counted as passing.
3. **A `failed` frontmatter value does not block.** `failed_phases` is unioned into the required set
   (:1099-1101), and that is all it does. A required phase is outstanding only when its latest entry
   is not passing (:1036-1050). The frontmatter said `failed`, and the verdict never consults it
   again.
4. **The run's own knowledge of the failure is dropped too.** The blocker went through the failure
   classifier. A `cross_agent` result pushes the phase to `skippedPhases` and breaks out of the
   retry loop (:2469-2475). `skippedAgents` is consulted only to word the reason when a phase has
   no entry at all (:1021). Inferred: this was the route, since the run continued to the
   completion step rather than returning `blocked`.

Entry timestamps would not have saved it. Ticket 05 of the same epic carries out-of-order
timestamps written by the agents themselves (for example `15:50` after `20:00`), so they cannot be
the ordering key either.

## Impact

`done` satisfies `depends_on` for every dependant (planner rule 2, `build-feature.js:3078`), so the
phantom close would have released tickets that need BO-4300f-4's proof. It was caught only because
the coordinator read the ticket against the AC store. `check-ticket-ac-status-parity` would have
refused the commit, but only once someone tried to commit, and the completion write uses
`--no-stage`, so the `done` state can sit unstaged in the worktree until then.

## Detection

After any drive, list tickets whose `status: done` coexists with any `agents:` value of `failed`
or `needed`, or whose `source_ac` is not `work_status: done`. In the Comments section, look for a
`### ` sign-off heading that sits after a level-2 heading other than `## Comments`.

## Fix direction

- Make the frontmatter decide. Any phase whose `agents:` value is `failed` or `needed` is
  outstanding, whatever its Comments entries say.
- Decide "latest" by something the writer cannot misplace. Either append through a script that
  writes at the end of the file, or have the read-back return the line number of each heading and
  refuse when an older entry follows a newer one.
- Carry the run's own skip or failure of a phase into the verdict, so a `cross_agent` skip of a
  gate makes that gate outstanding.
- Stop agent templates from writing level-2 headings inside `## Comments`. Make architect-review's
  `## Escalation` a bold label or a `####` heading.
- Add a test with a ticket whose gate has an old ok entry, a newer blocker entry placed above it,
  and `failed` in the frontmatter. The completion decision must refuse.

**Related.** `KI-SS-002` (the commit phase runs after a failed gate) is the same family: a failure
signal that the drive computes and then does not consume. `KI-BO-20260831-1931` is the opposite
direction of the same per-agent-latest-comment rule. `KI-BO-20260831-1932` recorded the lenient
completion write as phantom-done before BO-400e-3.
