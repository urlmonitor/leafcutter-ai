---
title: "GE-120f-1, -i and -ii are closed, with the defects their finalization hit on record"
date: "2026-09-28"
time: "09:00"
type: manual
components: 
  - build_orchestration
  - supervisor_system
  - security_scanner
summary: "The three GE-120f-1 tickets are marked done now that PR #916 is merged, and the defects met while committing and finalizing them are recorded as known issues."
description: "Tickets 01-03 of EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs move to status done; the rest of the epic stays open. Two known issues are new: the commit phase is signed off before the commit exists (KI-SS-20260927), and GENERIC_SECRET flags placeholder constants by name (KI-SEC-20260927). Three existing ones gain an occurrence: finalize-feature still sends shell steps to status-checker (KI-BO-20260901-1620), a bare pytest run skips the ac_store tests (KI-TQ-20260927), and working-copy CRLF blocks the parity hooks (KI-BP-20260910-1240). The finalization was done by hand because /finalize-feature stopped at triage for the first of these reasons."
breaking: false
---

## Entry

PR #916 landed GE-120f-1, GE-120f-1-i and GE-120f-1-ii, and this change closes their three tickets. The other six tickets in the epic, starting with the enrolment work in GE-120f-4, are still open.

The known issues come from committing and finalizing that work. The commit phase had to be recorded in a second commit, because the sign-off protocol writes "committed" before the commit exists. A placeholder constant was blocked as a secret because of its name. /finalize-feature sent three shell steps to an agent that refuses them and carried on to triage without the data triage needs, so it was stopped and the remaining steps were done by hand.
