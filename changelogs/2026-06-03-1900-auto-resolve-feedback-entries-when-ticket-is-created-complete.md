---
title: "Auto-resolve feedback entries when ticket is created complete"
date: "2026-06-03"
time: "19:00"
type: ticket_completion
components: 
  - build_pipeline
summary: "link_feedback.py now auto-resolves feedback entries when a ticket is created from them"
description: "Extended link_feedback.py with auto-resolve call gated on --ticket flag. Updated ticket-wiring skill with Step 3b and business-analyst with Step 1.5 for surfacing related unresolved feedback. Added --json flag to aggregate.py."
commits: 
  - 339a75c
ticket: "TICKET-20260603-AutoResolveFeedbackOnTicketCreate"
---

## Entry
