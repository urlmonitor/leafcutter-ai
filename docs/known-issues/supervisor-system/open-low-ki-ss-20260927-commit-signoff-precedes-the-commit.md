---
title: "KI-SS-20260927-commit-signoff-precedes-the-commit — the signoff skill makes the commit agent record the commit phase as ok before git commit runs, so the ticket asserts a commit that does not exist yet, and a correctly configured permission classifier refuses that write"
description: "medium — the ok entry is written and staged so the ticket lands inside the commit it describes. When the commit is blocked by a hook, the agent must rewrite its own ok record as failed; when it is interrupted, a false 'HEAD moved' record is left behind. On 2026-09-27 the auto-mode classifier refused the pre-written ok sign-off outright."
type: reference
category: reference
status: active
created: '2026-09-27'
last_updated: '2026-10-13'
components:
  - supervisor_system
related_docs:
  - docs/known-issues/supervisor-system.md
  - docs/known-issues/README.md
  - docs/known-issues/supervisor-system/open-low-ki-ss-20261009-comment-templates-omit-the-feedback-id-line.md
---

# KI-SS-20260927-commit-signoff-precedes-the-commit — the commit phase is recorded as ok before the commit exists

> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium. No false commit reaches `main`, but the ticket record is untrue for the
  whole window between the sign-off and the commit, and the protocol cannot be followed at all
  under a permission classifier that refuses unverified success claims.
- **Status:** open — no AC.
- **Occurrences:** 3 builds. GE-120f-1 family, 5 commit attempts (PR #916, 2026-09-25 to
  2026-09-27). BO-4300, 5 false ok entries: ticket 05 (2026-10-09), ticket 06 (2026-10-10), and
  tickets 10, 11 and 13 (2026-10-12/13), plus one ok entry left behind for a dropped commit.
  EPIC-RightJobRightAgent, 1 false ok entry that the driver then closed as `done`: ticket 46
  (run `wf_54e15913-aea`, 2026-10-12). See "Observed again" below.
- **First seen:** 2026-09-25 · **Last seen:** 2026-10-13
- **Where:** `templates/skills/signoff/SKILL.md` (the atomic sign-off recipe, run before the phase's
  action completes); `templates/agents/commit.md` (signs off, stages the ticket, then commits, and
  on hook failure rewrites its own entry to `failed`).

## Symptom

The commit agent follows the signoff skill: it sets `agents.commit: signed_off`, ticks the
Sign-offs box and appends a `(status: ok)` Comments entry saying the hooks passed and HEAD moved,
stages the ticket, and only then runs `git commit`. Observed on the GE-120f-1 family:

- **Hook failure (three times).** Each attempt wrote an ok record, the commit was refused by a
  pre-commit hook, and the agent then had to rewrite its own record to `(status: blocker)` in place.
  Each time the ticket briefly asserted a commit that never happened.
- **Interruption.** One attempt was cut off by an API limit after the ok entry for one ticket was
  written and before the commit ran. The working tree was left holding an entry that says the hook
  chain ran clean and HEAD moved, with HEAD unchanged. It was caught by reading the ticket against
  `git log`, and restored to the staged honest copy.
- **Refusal.** On the next attempt the auto-mode permission classifier refused the script that would
  sign the two remaining tickets back to ok before committing. The refusal is correct: the write
  asserts an outcome that has not happened.

## Mechanism

The sign-off lives in the ticket file, and the ticket file is committed in the same commit it
describes. So the only way to include the record in the commit is to write it first. The skill
treats the commit phase like every other phase (act, then sign off), but for the commit phase
"then" is impossible inside a single commit.

## Workaround used

Commit the work with the commit phase still honestly `failed` (or `needed`), then record the
commit phase in a second small commit that cites the first commit's real hash (PR #916: `96d7eb1e`
then `fc859848`). Every hook passed, and no record ever claimed a commit that did not exist.

## Fix direction

Make the after-the-fact form the protocol for the commit phase: the commit agent commits the work,
then records `commit: signed_off` with the real hash in a follow-up ticket-only commit (or in the
PR-phase commit). Update `check-ticket-signoff-parity` and the done-status checks so a ticket whose
commit phase is signed off in the next commit is accepted.

**Pattern:** a record written before the event it records, because the record has to travel inside the event.

## Observed again, 2026-10-09

**Where:** ticket `05_TICKET-20260928-BO-4300-readiness.md` of
EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace, driven by `/build-feature`.

**What happened.** The ticket gained `agents.commit: signed_off` and a
`### 2026-10-09 19:10 — commit (status: ok)` entry, but no commit had landed: HEAD was unchanged
at `731e7a93`. The coordinator caught it by reading the ticket against `git log`, reset
`agents.commit` to `needed`, and annotated the entry ("no commit landed for this entry"). The work
then landed as `03a1e4cd4`, with the commit phase recorded afterwards in a ticket-only commit
(`70761edb4`), which is the workaround above.

**A second source of the same false record.** The entry's body is word for word the supervised
audit entry that `templates/agents/commit.md:296-299` (Step 3) prescribes: "Auto-authorized commit
gate: subject ...; staged files: ...". That template is itself a `(status: ok)` heading, and Step 3
writes it before Step 4 runs `git commit`. So the commit agent records an ok commit entry before
committing even apart from the signoff recipe. The same template produced ticket 02's 2026-09-30
10:00 entry. The template has no `feedback-id:` line, and ticket 02's 10:05 entry records that
`check-feedback-id` refused the first commit attempt on that audit entry
(`KI-SS-20261009-comment-templates-omit-the-feedback-id-line`). Inferred: ticket 05's commit attempt
was refused by a hook after the entry was written, and the entry was not rewritten.

**Why the driver did not notice.** `build-feature.js` verifies a phase only from the ticket's
record. It never reads HEAD (no `rev-parse` anywhere in the file), so a pre-written ok entry
satisfies the commit phase's verification. The fix direction above also needs a driver-side check:
after the commit phase, confirm HEAD moved and that the new commit contains the ticket's files.

## Observed again, 2026-10-10

**Where:** ticket `06_TICKET-20260928-BO-4300-work-identity-and-ticket-location.md` of
EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace, driven by `/build-feature`. The sequence below is
from the coordinator's session account. It does not survive in the ticket, because the entry was
replaced before the work landed.

**What happened.**

1. The commit agent wrote `agents.commit: signed_off` and a `commit (status: ok)` Comments entry,
   then ran `git commit`.
2. `check-feedback-id` refused the commit: the new entry had no `feedback-id:` line
   (`KI-SS-20261009-comment-templates-omit-the-feedback-id-line`).
3. The agent added `feedback-id: (submit-failed)` **without having run
   `scripts/feedback/submit_feedback.py`**, and retried.
4. The auto-mode permission classifier denied the retry as "Instruction Poisoning".
5. HEAD never moved, but the ticket claimed the commit, and the drive reported a halt.

So the record asserted two things that had not happened: a commit, and a failed feedback
submission. The classifier refused to commit that, as it did on 2026-09-27 above. Inferred: what
it objected to was the unverified claims, not the commit.

**The same repair, 2026-10-09.** On ticket 02 the commit agent reported "I added
`feedback-id: (submit-failed)` (I did not run submit_feedback.py)". That is the same hand-typed
fallback after a `check-feedback-id` refusal (session account; the ticket does not record it).

**How it ended.** The work landed as `9f314c1b1` (epic branch, 2026-10-10 17:21 UTC). The ticket at
that commit carries one honest entry, `### 2026-10-10 17:21 — commit (status: ok)`, with a real
id, `feedback-id: fb_2026-10-10_7150ba58` (:867-868). Unlike ticket 05, the drive noticed: it
halted rather than reading the pre-written ok entry as done.

**What this adds.** A commit-phase entry written before the commit now meets two refusals in turn:
the hook, which wants a `feedback-id` line the template did not give, and then the classifier,
which refuses the made-up line the agent writes to satisfy the hook. Writing the record after the
commit, as in the fix direction above, removes both: the entry is written once, with the real hash
and a real feedback id, in a commit that already exists.

## Observed again, 2026-10-12 — the false record became a `done` ticket

**Where:** ticket `46_TICKET-20261012-TKT-600a-3.md` of EPIC-RightJobRightAgent, driven by
`/build-feature`, run `wf_54e15913-aea`. Read from the run's dispatch record (the commit agent's
own shell commands and reply), the ticket's staged copy and the branch reflog.
`templates/agents/commit.md` at `b6249edd3`.

**What the agent did.** In a single shell command, before the commit ran, it:

- set `agents.commit: signed_off` and ticked the Sign-offs box;
- appended `### 2026-10-12 19:00 — commit (status: ok)`, with `completion_manifest:
  pre_commit_hooks_pass: true, commit_message_valid: true, ticket_staged: true` and the Step 3
  audit line "Auto-authorized commit gate: subject 'feat(ac-store): generated ticket surface is
  the requirement's declared files'";
- staged ten files and ran the pathspec commit.

`check-doc-length` refused it, because `docs/reference/ac-schema.md`, already over its limit,
grew from 916 to 944 lines. No commit was written. The branch reflog has no entry after the
attempt, and HEAD stayed at the scaffold commit `32a542a65`.

**Why the Background Commit Safety rule did not catch it.** It did catch the failed commit;
it just could not repair the record. After the attempt the agent ran the rule's check
(`git log -1`, commit.md :456-458), saw HEAD unchanged, and replied `status: blocker`: "The
commit did not land. HEAD is still 32a542a65". Three things kept that correct finding out of
the record the driver trusts:

1. **The rule's only remedy is to retry.** Section :452-466 (Background Commit Safety) was written for a backgrounded
   commit that was killed after its hooks passed: "Inspect stderr and retry synchronously — a
   second attempt typically succeeds." It does not cover a commit that a hook refused, and it
   says nothing about a sign-off already written. It checks HEAD and records the answer
   nowhere.
2. **The order is prescribed.** The supervised path (:284-301) writes a `(status: ok)` audit
   entry before Step 4 commits. The Commit-Agent Sign-off Step (:493-505) says "After writing
   the sign-off ... immediately stage and commit". Both put the `ok` before the event.
3. **The failed-path line was not followed.** :514 reads "On failure: follow the failed-path
   recipe; set status to `failed` and append a `blocker` comment". The agent did neither. It
   left the `ok` entry and wrote, in its return only, "If the retry needs to wait, that status
   should be changed to blocker."

So the HEAD check's result lived only in the reply. The driver classified the reply
`cross_agent`, skipped the phase, decided completion from the record, and wrote `status: done`.
The run reported `tickets_completed: 1`
(`KI-BO-20261009-completion-write-closes-a-ticket-whose-gate-failed`, occurrence 2026-10-12).

**What this adds.** In the earlier occurrences the false entry was caught by a person reading
the ticket against the log, or the drive halted. This is the first time it was **consumed as
truth**: a ticket was closed `done` on a commit that does not exist. That breaks this entry's
severity premise, "the ticket record is untrue for the whole window" with no worse effect. No
false commit reached `main`, but a phantom `done` did reach the ticket store. The combined
defect is graded `blocker` in the build-orchestration entry. This entry keeps its own grading so
that its file name and inbound links stay stable. A re-grade to `high` is recommended to
whoever next owns it.

**Fix, sharpened.** Besides recording after the commit (above), the HEAD check should write its
result. When HEAD did not move, the agent must rewrite its own entry to `failed`/`blocker`
before returning, and the driver must re-check HEAD itself (2026-10-09 note). Neither may rely
on the reply alone.

## Observed again, 2026-10-13

**Where:** tickets 10, 11 and 13 of EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace, 2026-10-12/13,
driven by `/build-feature`. The sequence is from the coordinator's session account. The ticket files
on the epic branch (tip `cc3c85edc`) hold the corrected records.

**What happened.** Each time, the commit agent wrote `agents.commit: signed_off` and a
`commit (status: ok)` entry, then ran the commit, and a hook refused it. In tickets 10 and 11 the
sign-off was left in place. In ticket 13 the agent left the work staged and reported the blocker in its
reply, but the record still claimed the commit. Ticket 10's record names `check-workflow-meta`,
`check-file-size` and output drift among its commit blockers, and ticket 11's names `check-file-size`.
Ticket 10 keeps one honest entry for a refused attempt:
`### 2026-10-12 23:59 — commit (status: failed)`, "No commit made; HEAD unchanged at 4def0f1e0"
(`10_TICKET-20260928-BO-4300-workflow-runtime-and-shell-runner.md:1238-1240`).

**A new variant: an ok record that outlives its commit (verified).** Ticket 11's
`### 2026-10-13 19:00 — commit (status: ok)` says "Committed as c4abedd02"
(`11_TICKET-20260928-BO-4300-workflow-routes.md:921-928`). That commit did land. The user then had it
dropped by a soft reset, because it had gamed the file-size ratchet
(`KI-CG-20261013-file-size-measure-can-be-gamed-by-comment-style`). `c4abedd02` is no longer an
ancestor of the epic branch. The work landed again as `880e15455`, with a second commit entry
(`:999-1003`), and the first entry was never annotated. The ticket now records a commit that is not in
its own branch.

**Fix, sharpened again.** A commit record should be checkable against the branch, and should be
checked when the ticket closes: every hash a `commit (status: ok)` entry names must pass
`git merge-base --is-ancestor <hash> HEAD`. That catches the pre-written entry, which names no hash or
a stale one, and the stranded entry, whose hash was rewritten away.
