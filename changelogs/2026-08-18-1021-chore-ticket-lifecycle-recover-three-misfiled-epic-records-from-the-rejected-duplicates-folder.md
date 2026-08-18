---
title: "chore(ticket-lifecycle): recover three misfiled epic records from the rejected-duplicates folder"
date: "2026-08-18"
time: "10:21"
type: manual
components: 
  - ticket_lifecycle
summary: "Four old project folders had been flagged as duplicate copies and set aside for deletion; a closer check found three of them were not duplicates at all and held records that existed nowhere else, so those were rescued before the folder was cleared out."
description: "A prior sweep (PR #275) moved four epic folders into tickets/99_rejected/ as duplicates of copies already marked done. Re-checking each against git history and the live codebase found three were misfiled: one had its labels backwards (the 'official' copy was blank pre-work, the 'duplicate' held the only reviews, approvals and commit references); one folder name was reused by two unrelated epics three days apart, so the second epic's plan file was mistaken for a stale copy and deleted along with it (now recovered under a distinct filename with a table mapping tickets to plans); and one 'empty' folder's single file was in fact its epic's only plan, while the 'official' copy had tickets but no plan. Five ticket statuses were corrected from not-started to done, each only after confirming the promised work is actually present in the codebase; one ticket was deliberately left not-started because the file it targeted no longer exists. No approvals were invented — tickets note plainly where work arrived outside the normal review process. tickets/99_rejected/ is now empty."
commits: 
  - 3ef5c3aa8
breaking: false
---

## Entry

A prior cleanup pass (PR #275) moved four old epic folders into a
rejected-duplicates holding area, on the assumption that each one was just a
stale copy of a record already filed as done elsewhere. Re-checking each
folder against its git history and against the actual codebase found that
three of the four were not duplicates at all, and would have been permanently
lost had the folder simply been deleted.

One epic's "official" done copy turned out to be blank pre-work templates,
while the copy that had been marked as the duplicate held the only reviews,
approvals, and commit references for work that is genuinely live in the
codebase today — the labels were exactly backwards.

One epic folder name had been reused twice, three days apart, by two
unrelated pieces of work. Both plan files were named the same thing and
differed only in their title line, so the second one was read as a stale
copy of the first and discarded along with it — taking the only record of
that second effort with it. It has been recovered under its own name, with a
table at the top making clear which tickets belong to which plan.

One folder that looked empty (a single file, no tickets) turned out to hold
that epic's only plan document — the copy marked "official" had five tickets
but no plan at all. Deleting the folder would have destroyed it.

Alongside the recovery, five ticket records were corrected from not-started
to done, each only after confirming the promised work is actually present in
the codebase. One ticket was deliberately left as not-started, because the
file it was supposed to change no longer exists — the work was superseded
rather than completed, and marking it done would have claimed something
untrue. No approvals or sign-offs were invented anywhere; where work arrived
outside the normal review process, the record says so plainly instead of
showing fabricated approvals.

The rejected-duplicates folder is now empty.
