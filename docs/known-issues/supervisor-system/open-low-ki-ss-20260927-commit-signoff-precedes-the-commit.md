---
title: "KI-SS-20260927-commit-signoff-precedes-the-commit — the signoff skill makes the commit agent record the commit phase as ok before git commit runs, so the ticket asserts a commit that does not exist yet, and a correctly configured permission classifier refuses that write"
description: "medium — the ok entry is written and staged so the ticket lands inside the commit it describes. When the commit is blocked by a hook, the agent must rewrite its own ok record as failed; when it is interrupted, a false 'HEAD moved' record is left behind. On 2026-09-27 the auto-mode classifier refused the pre-written ok sign-off outright."
type: reference
category: reference
status: active
created: '2026-09-27'
last_updated: '2026-09-27'
components:
  - supervisor_system
related_docs:
  - docs/known-issues/supervisor-system.md
  - docs/known-issues/README.md
---

# KI-SS-20260927-commit-signoff-precedes-the-commit — the commit phase is recorded as ok before the commit exists

> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium. No false commit reaches `main`, but the ticket record is untrue for the
  whole window between the sign-off and the commit, and the protocol cannot be followed at all
  under a permission classifier that refuses unverified success claims.
- **Status:** open — no AC.
- **Occurrences:** 1 build, 5 commit attempts (GE-120f-1 family, PR #916, 2026-09-25 to 2026-09-27)
- **First seen:** 2026-09-25 · **Last seen:** 2026-09-27
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
