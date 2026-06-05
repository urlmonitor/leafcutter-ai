---
title: "Register templates/commands/ in build parity test allow-list complete"
date: "2026-06-05"
time: "16:00"
type: ticket_completion
components: 
  - build_pipeline
summary: Added commands to non_artifact_dirs in test_build_artifact_parity.py
description: Added commands to the non_artifact_dirs exemption set in test_build_artifact_parity.py so the build parity test suite passes after templates/commands/ was introduced.
pr: 64
commits: 
  - afd0932
  - f7977cf
  - 0c3edde
  - b42ac63
  - 4a2760f
ticket: "TICKET-20260605-BuildParityCommandsDir"
---

## Entry
