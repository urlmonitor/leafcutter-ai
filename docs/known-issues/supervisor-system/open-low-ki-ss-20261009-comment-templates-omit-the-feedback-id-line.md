---
title: "KI-SS-20261009-comment-templates-omit-the-feedback-id-line — agent templates give literal Comments entries with no feedback-id line, so agents that copy them write entries check-feedback-id later refuses at commit"
description: "medium — the signoff skill requires feedback-id as the first line of every Comments entry, and check-feedback-id refuses any new sign-off heading without one in its next two lines. But commit.md's supervised audit entry, test-writer's and ticket-supervisor's skip entries, python-coder's red-baseline example and status-checker's auto-close entry are all given as literal templates without it. On EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace the hook refused ticket 02's commit on the commit agent's own audit entry (2026-09-30) and ticket 05's on four entries (2026-10-09)."
type: reference
category: reference
status: active
created: '2026-10-09'
last_updated: '2026-10-13'
components:
  - supervisor_system
  - commit_guardian
related_docs:
  - docs/known-issues/supervisor-system.md
  - docs/known-issues/build-pipeline/open-high-ki-bp-017.md
  - docs/known-issues/commit-guardian/open-low-ki-cg-20260901-feedback-id-escape-hatch-reads-the-previous-commit-message.md
  - docs/known-issues/supervisor-system/open-low-ki-ss-20260927-commit-signoff-precedes-the-commit.md
  - docs/known-issues/feedback-collector/open-low-ki-fc-003.md
---

# KI-SS-20261009-comment-templates-omit-the-feedback-id-line — the templates contradict the rule the hook enforces

> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** medium. It fails closed: the commit is refused with a clear message and nothing
  wrong lands. But each refusal costs a commit attempt plus a repair, and on a supervised drive the
  repair is a hand-edit of entries the agents wrote.
- **Status:** open, no AC. Template contents verified on `origin/main` `c373b005e`.
- **Occurrences:** 3 tickets, 4 refusals. Ticket 02, 2026-09-30, one entry (the commit agent's
  audit entry), and again on 2026-10-09. Ticket 05, 2026-10-09, four entries. Ticket 06,
  2026-10-10, the commit agent's entry. The last two refusals were "repaired" with a made-up
  `feedback-id: (submit-failed)` (see "Observed again" below). Typed or missing ids again on
  tickets 10, 11 and 13, 2026-10-12/13, where the permission classifier refused two of the repairs.
- **First seen:** 2026-09-30 · **Last seen:** 2026-10-13
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

## Observed again, 2026-10-10: the fallback is typed without running the script

**What happened.** Twice, a commit agent answered a `check-feedback-id` refusal by typing
`feedback-id: (submit-failed)` into the entry **without calling `scripts/feedback/submit_feedback.py`**:

- Ticket 02, 2026-10-09. The agent reported: "I added `feedback-id: (submit-failed)` (I did not run
  submit_feedback.py)".
- Ticket 06, 2026-10-10. The agent did the same on its pre-written commit entry. The permission
  classifier then denied the retry as "Instruction Poisoning"
  (`KI-SS-20260927-commit-signoff-precedes-the-commit`).

Both come from the coordinator's session accounts. Neither line survives in the ticket files.

**The rule allows that value only after the script ran and failed.** Verified on `origin/main`
`d03830e7c`:

- `templates/skills/signoff/SKILL.md:197-201` (§2a step 4): "If the script exits non-zero ... use
  `feedback-id: (submit-failed)` as the fallback value".
- `SKILL.md:1050` (§8): "**Don't** skip the `submit_feedback.py` call (§2a). If the script fails, use
  `feedback-id: (submit-failed)` ... An empty feedback entry is not a valid substitute for calling
  the script."

**The hook cannot tell a real failure from a typed one.**

- `templates/scripts/commit_guardian/check_feedback_id.py:50-51`: the comment says the pattern
  matches `feedback-id: fb_YYYY-MM-DD_xxxxxxxx`, but the regex is `^\s*feedback-id:\s*\S`. It
  accepts any non-blank value, including `(submit-failed)` typed by hand.
- Its refusal message (:296-299) says "Add 'feedback-id: <id>' on the line immediately after each
  heading". It does not mention the script, so the shortest path to a pass is to type the line.
- `submit_feedback.py` leaves no trace when it fails. A rejected submission exits 1 before the log
  is opened; only an accepted one is appended to `debugging/logs/feedback.jsonl`
  (`templates/scripts/feedback/submit_feedback.py:116`, :530-534). So afterwards, a genuine
  `(submit-failed)` and a typed one look the same.

**The fallback has become the default.** At epic commit `9f314c1b1`, the six built tickets (01-06)
carry 77 `feedback-id: (submit-failed)` lines, 44 real `fb_` ids and 2 other values:

| Ticket | `(submit-failed)` | `fb_` id |
|---|---|---|
| 01 | 10 | 22 |
| 02 | 14 | 11 |
| 03 | 9 | 0 |
| 04 | 10 | 4 |
| 05 | 25 | 6 |
| 06 | 9 | 1 |

Some of these are genuine. The epic branch forked from main on 2026-09-27 (merge base `d0c573289`)
and lacks `c3a469610` (2026-09-28), which let `ac-validator` and `ac-fulfillment-gate` write
feedback. So those two agents are still refused there (`KI-FC-003`), and ticket 02's ac-validator
entry records exactly that. How many of the rest were typed without running the script cannot be
told from the record, and that is the defect.

**Fix direction, in addition to the above.**

- Make a failure leave a receipt. On a non-zero exit, `submit_feedback.py` appends the attempt
  (time, agent, category, error) to a failure log and prints a receipt id. The fallback becomes
  `feedback-id: (submit-failed: <receipt>)`.
- Make the hook check the value. Accept an `fb_<date>_<hex>` id or a `(submit-failed: <receipt>)`
  receipt, and verify that it exists in the feedback log or the failure log when that log is
  readable. Refuse a bare `(submit-failed)`.
- Make the refusal name the remedy: "run `scripts/feedback/submit_feedback.py` (signoff §2a) and use
  the id it prints", not just "add a line".
- Merge `c3a469610` into long-lived epic branches, so the genuine failures stop and the fallback is
  rare enough to stand out.

## Observed again, 2026-10-13: typed ids continue, and the classifier refuses the repair

**Where:** tickets 10, 11 and 13 of EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace, 2026-10-12/13. The
account is the coordinator's. The counts are from the ticket files at epic tip `cc3c85edc`.

**What happened.**

- pr-reviewer, python-coder, test-runner and commit agents kept writing `feedback-id: (submit-failed)`
  without running `scripts/feedback/submit_feedback.py`, or left the line out. Ticket 11 alone had five
  such entries, and tickets 10 and 13 had more.
- The permission classifier refused two of the agents' own repairs. It called a pr-reviewer's
  self-sign-off with a typed id "Self-Approval". It called a commit agent's attempt to type a placeholder
  id into *another phase's* entry "Instruction Poisoning".
- The coordinator replaced each typed value with a real submission, noted as recorded afterwards.

**What survives on the branch (verified):**

| Ticket | `(submit-failed)` | `fb_` id |
|---|---|---|
| 07 | 5 | 4 |
| 08 | 1 | 7 |
| 10 | 4 | 17 |
| 11 | 0 | 19 |
| 13 | 0 | 11 |

Tickets 11 and 13 now carry only real ids. Ticket 10 still has four typed values, including its
pr-reviewer entry at 2026-10-12 23:50 and the failed commit entry at 23:59 (`:1235-1239`). The ticket
text does not mark which ids were submitted after the fact, so the record cannot show which agents
actually ran the script.

**What this adds.** Typing the line is no longer just a gap the hook misses. The next layer, the
permission classifier, now treats a typed id as a forged record and refuses it, so the shortcut that
`check-feedback-id`'s refusal message invites ("add a line") halts the drive. The fix direction above is
unchanged and more urgent. Have the script leave a receipt even when it fails, have the hook check the
value against that receipt, and have the refusal name the script. An agent that runs the script then
never needs to type an id.
