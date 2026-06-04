---
title: "Fix _resolve_precommit_cmd() to validate known-path candidates before use complete"
date: "2026-06-04"
time: "23:59"
type: ticket_completion
components: 
  - build_pipeline
summary: "Validate pre-commit known-path candidates with --version probe before use"
description: "Added --version probe to _resolve_precommit_cmd() tier-3 known-paths loop so stale or non-executable binaries are skipped instead of causing a misleading error. When no valid pre-commit binary exists, install_hooks() now emits a clear warning with pip install remedy instructions."
pr: 56
commits: 
  - 6b0441d
  - 8921616
  - 0bec1bb
ticket: "TICKET-20260604-PrecommitBinaryResolution"
---

## Entry
