---
title: "KI-BO-20261009-completion-write-closes-a-ticket-whose-gate-failed — /build-feature wrote status: done on a ticket whose ac-fulfillment-gate had just failed and whose AC was still todo, because the completion decision takes the gate's last entry by file position and a blocker entry was inserted above an older ok"
description: "low since 2026-10-14 (was blocker) — the phantom-done routes are closed by BO-400a-2-v (PR #1201) and the misplacing level-2 headings are gone from the agent templates; what remains is that 'latest entry' still means last in file order. Original: phantom-done at the orchestration layer. On 2026-09-30, ticket 02 of EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace was set to status: done while agents.ac-fulfillment-gate read failed and its source AC BO-4300f-4 read work_status: todo. The gate's new blocker entry had been written above its older ok entry (just before a level-2 '## Escalation' heading inside an earlier comment), and completionVerdictFromRecord reads the last entry in file order, so the gate counted as passed. A frontmatter value of failed only adds a phase to the required set; it never makes it outstanding."
type: reference
category: reference
status: active
created: '2026-10-09'
last_updated: '2026-10-14'
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

- **Severity:** low since 2026-10-14 (filename bucket moved from `blocker` to `low`). The original
  grading, kept as written: blocker. This is the phantom-done failure the package exists to
  prevent, and it happened in the driver's own completion decision. Nothing in the run output
  says that a failed gate was overridden. The ticket simply reads `done`, and `done` releases its
  dependants.
- **Status:** open, mostly fixed. See "Status update, 2026-10-14" at the end. Mechanisms 3 and 4
  are fixed by BO-400a-2-v (PR #1201). Mechanism 1's cause, level-2 headings that agent templates
  told agents to write into their comments, is removed by BO-400a-2-vi. Mechanism 2 (the latest
  entry is the last one in file order) is still open. Original status line: open, no AC.
  Mechanism verified by reading `origin/main` `c373b005e` and the ticket's committed history.
  The insertion cause (below) is inferred from the file positions.
- **Occurrences:** 2. Ticket `02_TICKET-20260928-BO-4300-deployed-maker-test-support.md`,
  2026-09-30, the run between commits `08d190daf` (22:50 UTC) and `45e6f2268` (23:06 UTC) on branch
  `epic/every-piece-of-separate-work-gets-its-workspace`. Then ticket
  `46_TICKET-20261012-TKT-600a-3.md`, run `wf_54e15913-aea`, 2026-10-12, where the closed phase
  was `commit` and the route in mechanism 4 is confirmed. See "Observed again, 2026-10-12".
- **First seen:** 2026-09-30 · **Last seen:** 2026-10-12
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

## Observed again, 2026-10-12 — the commit phase, closed with no commit

**Where:** `/build-feature` on EPIC-RightJobRightAgent, run `wf_54e15913-aea`, ticket
`46_TICKET-20261012-TKT-600a-3.md`. Line numbers are `templates/workflows-js/build-feature.js`
at `b6249edd3`, the script the run executed. Every step below is read from the run's dispatch
record, the ticket's staged copy and the branch reflog.

**Sequence.**

1. **The commit agent recorded success first.** In one shell command it set
   `agents.commit: signed_off`, ticked the Sign-offs box, and appended
   `### 2026-10-12 19:00 — commit (status: ok)` with `completion_manifest:
   pre_commit_hooks_pass: true` and "Auto-authorized commit gate: subject 'feat(ac-store):
   generated ticket surface is the requirement's declared files'". Then it staged ten files and
   ran a pathspec commit (`KI-SS-20260927-commit-signoff-precedes-the-commit`, occurrence
   2026-10-12).
2. **The hook refused the commit.** `check-doc-length` refused
   `docs/reference/ac-schema.md`, which was already over its 300-line limit and grew from 916 to
   944 lines (the hook counts lines without frontmatter; the whole file went from 931 to 959).
   The agent's report calls this "the pre-commit file-size check". The ratchet wording is
   `check_doc_length.py`'s, and the body is 916 lines at HEAD. The 28 lines came from
   `documentation-expert` authoring the doc itself on this ticket
   (`KI-BO-20261012-documentation-expert-cannot-reach-its-specialists-in-the-flat-driver`).
3. **The agent told the truth in its return.** It checked HEAD and replied `status: blocker`:
   "The commit did not land. HEAD is still 32a542a65 ... If the retry needs to wait, that status
   should be changed to blocker." It left the `ok` record in place.
4. **The classifier saw the problem, and the driver discarded what it said.** The failure
   classifier returned `cross_agent` (the fix belongs to `documentation-expert`). Its reason
   text adds "ANOMALY 1: ... this false `ok` entry would let the ticket look finished with
   nothing committed" and "ANOMALY 2: ... the cross_agent branch only skips the phase. It never
   re-runs the named sibling". The driver reads only `classification`.
5. **The skip, then the close.** `cross_agent` pushes `commit` to `skippedPhases` and breaks
   (:2469-2475). `concludeTicket` (:1503) asks `completionVerdictFromRecord` (:957). The latest
   `commit` entry reads `ok`, so it passes (:1035). `skippedAgents` is consulted only to word
   the reason for a phase with no entry (:1021). The verdict is complete. `writeTicketCompletion`
   (:1522) wrote `status: done`, and the outcome carried `ticket_completed: true`. The run then
   reported `tickets_completed: 1` and listed ticket 46 in `completed_batches`.
6. **No commit exists.** The branch reflog has no entry after the attempt, HEAD stayed at the
   scaffold commit `32a542a65`, and the ticket's ten files stayed staged. They then tripped the
   staged-leftovers stop that ended the run
   (`KI-BO-20261009-one-halted-ticket-stops-the-whole-epic-run`, occurrence 2026-10-12).

**What this adds.**

- **Mechanism 4 is no longer inferred.** The record shows the `cross_agent` verdict and then
  the completion write on the same ticket.
- **The phase it closed is `commit`.** That is the phase meant to be the last word on a ticket,
  so the phantom `done` here sits on work that is not in git at all.
- **The `done` would have been sticky.** A re-run's planner omits `status: done` tickets
  (prompt step 4, :3080), so the commit would never have been retried. `done` also satisfies
  `depends_on` for tickets 47 and 48.
- **The epic payload hides it.** The per-ticket outcome names the skipped phase
  (`skipped_phases`), but the epic return's `completed_batches` carries only paths. Detect it
  by checking each completed ticket against the branch log.

**Fix, in addition to the above.** `skip` is never a correct outcome for `commit`. A
`cross_agent` verdict on the commit phase must either dispatch the named sibling and re-run
`commit`, or refuse the ticket. It must never fall through to the completion decision. The
driver-side HEAD check that `KI-SS-20260927` asks for (2026-10-09 note) would also have caught
this on its own.

## Status update, 2026-10-14 — mostly fixed, downgraded to low

**Fixed: mechanisms 3 and 4, by BO-400a-2-v (PR #1201, merge `26ed98ef2`).** Both drivers
(`build-feature.js` and its twin `build-ticket.js`) now consult `failureSignalFor()` for every
required phase before reading its Comments entries. A phase whose frontmatter reads `failed`, or
that this drive skipped after a `cross_agent` blocker, is outstanding whatever entries the record
carries, and the not-completed report names the phase and the signal. Both recorded occurrences
are covered by behavioural tests that drive the real scripts
(`unit_tests/prompt_assembly/test_bo_400a_2_v.py`). A skipped `commit` phase can no longer reach
the completion write, which is the "Fix, in addition to the above" asked for in the 2026-10-12
section.

**Not changed, by decision: frontmatter `needed`.** A phase still marked `needed` is not treated
as a failure signal. The BO-400e-1 contract counts `needed` with a passing entry as satisfied, and
`scripts/set_ticket_status.py` already refuses to write `done` while any phase reads `needed`, so
that case cannot become a phantom done. In that case the drive still attempts the write and then
reports `outstanding_phases: []`, which is misleading. Not yet filed.

**Fixed: mechanism 1's cause, by BO-400a-2-vi.** `architect-review.md`, `conflict-resolver.md`
and `pr-reviewer.md` no longer tell the agent to append a level-2 `## Escalation` heading to its
output. They use a bold `**Escalation**` label instead, so no agent writes a level-2 heading into
a ticket's `## Comments` that a writer can mistake for the end of the section.

**Still open: mechanism 2.** "Latest entry" still means the last `### ` heading in file order.
An entry that lands out of order, for any other reason, is still read as the latest. With the two
signals above deciding first, the remaining exposure is a phase whose frontmatter does not say
`failed` and which this drive did not skip. That is why the bucket is now `low`. The fix direction
above (append through a script, or have the read-back return each heading's line number and refuse
when an older entry follows a newer one) still applies.
