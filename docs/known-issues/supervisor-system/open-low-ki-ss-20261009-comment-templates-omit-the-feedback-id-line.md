---
title: "KI-SS-20261009-comment-templates-omit-the-feedback-id-line — agent templates give literal Comments entries with no feedback-id line, so agents that copy them write entries check-feedback-id later refuses at commit"
description: "medium — the signoff skill requires feedback-id as the first line of every Comments entry, and check-feedback-id refuses any new sign-off heading without one in its next two lines. But commit.md's supervised audit entry, test-writer's and ticket-supervisor's skip entries, python-coder's red-baseline example and status-checker's auto-close entry are all given as literal templates without it. On EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace the hook refused ticket 02's commit on the commit agent's own audit entry (2026-09-30) and ticket 05's on four entries (2026-10-09)."
type: reference
category: reference
status: active
created: '2026-10-09'
last_updated: '2026-10-09'
components:
  - supervisor_system
  - commit_guardian
related_docs:
  - docs/known-issues/supervisor-system.md
  - docs/known-issues/build-pipeline/open-high-ki-bp-017.md
  - docs/known-issues/commit-guardian/open-low-ki-cg-20260901-feedback-id-escape-hatch-reads-the-previous-commit-message.md
  - docs/known-issues/supervisor-system/open-low-ki-ss-20260927-commit-signoff-precedes-the-commit.md
---

# KI-SS-20261009-comment-templates-omit-the-feedback-id-line — the templates contradict the rule the hook enforces

> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** medium. It fails closed: the commit is refused with a clear message and nothing
  wrong lands. But each refusal costs a commit attempt plus a repair, and on a supervised drive the
  repair is a hand-edit of entries the agents wrote.
- **Status:** open, no AC. Template contents verified on `origin/main` `c373b005e`.
- **Occurrences:** 2 tickets. Ticket 02, 2026-09-30, one entry (the commit agent's audit entry).
  Ticket 05, 2026-10-09, four entries.
- **First seen:** 2026-09-30 · **Last seen:** 2026-10-09
- **Where:** the rule: `templates/skills/signoff/SKILL.md:125` and `:743` ("`feedback-id:` line ...
  always first"); the gate: `templates/scripts/commit_guardian/check_feedback_id.py` (a new
  `### YYYY-MM-DD HH:MM — ` heading needs `feedback-id:` within its next two added lines). The
  templates that omit it:
  - `templates/agents/commit.md:296-299`, the supervised-path audit entry, written on every
    supervised commit.
  - `templates/agents/test-writer.md:254-257`, the non-code skip entry.
  - `templates/agents/ticket-supervisor.md:334-337` and `:358`, the skip and contract-shrinking
    entries.
  - `templates/agents/python-coder.md:331-336`, the red-baseline sign-off example.
  - `templates/agents/status-checker.md:223-226`, the auto-close entry.
  - The signoff skill's own worked examples (`SKILL.md:844-895`).

## Symptom

- **Ticket 02.** The commit agent's 2026-09-30 10:05 entry records: "The first attempt this
  session failed check-feedback-id on the audit entry lacking a feedback-id line; fixed by
  submitting feedback and adding the line, then the retry passed all hooks." The audit entry it
  means is the one `commit.md:297-298` prescribes, word for word ("Auto-authorized commit gate:
  subject ...; staged files: ...").
- **Ticket 05.** `check-feedback-id` refused the commit on four new Comments entries without the
  line. They were repaired by hand before `03a1e4cd4` landed.

## Mechanism

The signoff skill states the rule once, in prose. The agent templates give literal blocks to paste,
and a literal block wins over a rule stated elsewhere. The commit agent's case is the sharpest: its
audit entry is a required step on every supervised commit (`commit.md` Step 3), the template has no
`feedback-id` line, and the commit it precedes is the one the hook checks. So a commit agent that
follows its own template exactly will have its commit refused on the entry it was told to write.

## Impact

Every supervised ticket commit risks a refusal and a repair. On ticket 02 the repair meant calling
`submit_feedback.py` after the fact. The repair also edits entries the agents wrote, which weakens
the record as evidence of what each agent did. Many entries fall back to `feedback-id:
(submit-failed)` anyway (`KI-BP-017`), so the line is present without carrying an id.

## Fix direction

- Add `feedback-id: <id from §2a>` as the first body line of every literal entry template above,
  including the signoff skill's worked examples.
- Better: have one script append Comments entries (heading, `feedback-id`, body), and have every
  template call it rather than paste a block. That also fixes the insertion-position problem in
  `KI-BO-20261009-completion-write-closes-a-ticket-whose-gate-failed`.
- Add a template lint: every `### YYYY-MM-DD HH:MM — ` example in `templates/agents` and
  `templates/skills` must be followed by a `feedback-id:` line, or be marked as a heading-schema
  illustration.

**Related.** `KI-SS-20260927-commit-signoff-precedes-the-commit` (the same audit entry is also the
`(status: ok)` written before the commit runs). `KI-BP-017` (`scripts/feedback/` missing from
worktrees, so ids come back `(submit-failed)`). `KI-CG-20260901-feedback-id-escape-hatch-reads-the-previous-commit-message`
(the hook's bypass does not work with `git commit -m`).
