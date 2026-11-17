---
title: "A finished ticket's done status no longer stops the epic run or blocks the next commit"
date: "2026-10-08"
time: "09:00"
type: manual
components:
  - build_orchestration
summary: "When /build-feature or /build-ticket completes a ticket, the completion write now records status: done without staging the file (set_ticket_status.py --no-stage). A staged done ticket used to stop an epic run at the next halt and was swept into the next ticket's commit, where check-predone-scope blocked it. finalize-feature step 3.5 now resets to the branch HEAD on both paths, so it re-sets the done statuses, closes the source ACs and commits that closure before the merge."
description: "Found while building DK-400 E1: batch 1 completed a ticket, a later ticket halted, and the staged-leftovers stop (BO-100e-4) ended the run on the first ticket's staged done status. set_ticket_status.py gains --no-stage (the default still stages); both drivers' writeTicketCompletion pass it; status-checker's Closing protocol names the exception. Review then found that finalize-feature step 3.5 only ran merge --abort when its test merge was in progress, which keeps unstaged edits, so the unstaged done status would have made the closure skip the ticket; that path now also runs git reset --hard HEAD, like the no-merge path. build-feature-ops-notes KI-10 tells operators to leave the unstaged done tickets alone. Decided through the Decision Kernel (run run-f6524c703be24639) after the user approved the basis."
---

## Entry
