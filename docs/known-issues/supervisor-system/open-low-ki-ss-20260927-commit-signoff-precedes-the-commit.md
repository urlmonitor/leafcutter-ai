---
title: "KI-SS-20260927-commit-signoff-precedes-the-commit — the signoff skill makes the commit agent record the commit phase as ok before git commit runs, so the ticket asserts a commit that does not exist yet, and a correctly configured permission classifier refuses that write"
description: "medium — the ok entry is written and staged so the ticket lands inside the commit it describes. When the commit is blocked by a hook, the agent must rewrite its own ok record as failed; when it is interrupted, a false 'HEAD moved' record is left behind. On 2026-09-27 the auto-mode classifier refused the pre-written ok sign-off outright."
type: reference
category: reference
status: active
created: '2026-09-27'
last_updated: '2026-10-10'
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
- **Occurrences:** 2 builds. GE-120f-1 family, 5 commit attempts (PR #916, 2026-09-25 to
  2026-09-27). BO-4300, 2 false ok entries: ticket 05 (2026-10-09) and ticket 06 (2026-10-10). See
  "Observed again" below.
- **First seen:** 2026-09-25 · **Last seen:** 2026-10-10
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
