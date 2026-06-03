---
title: "Epic archive pre-flight: verify all sub-ticket statuses before archiving complete"
date: "2026-06-03"
time: "15:30"
type: ticket_completion
components: 
  - build_pipeline
summary: "Pre-archive validation skill for finalize-feature Step 5"
description: "Adds a pre-archive validation skill that scans epic done/ folders for sub-tickets missing status: done in frontmatter. Integrates into finalize-feature.js Step 5 with confirmation-gated auto-fix."
pr: 40
commits: 
  - fd0795c
  - f2fef95
  - 9f5124b
ticket: "TICKET-20260603-EpicArchiveStatusCheck"
---

## Entry
