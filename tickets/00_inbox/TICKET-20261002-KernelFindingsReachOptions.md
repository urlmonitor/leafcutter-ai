---
title: "Kernel: synthesis findings reach the option-generation request"
status: todo
components:
  - decision_kernel
created: 2026-10-02
depends_on: []
priority: medium
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - decision-kernel
last_updated: 2026-10-02
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Kernel: synthesis findings reach the option-generation request

## Actor / Goal
In order that options are generated from what synthesis just concluded, we need the `generate_options` request to carry the findings the host submitted.

## Context
- **Live reproduction:** in runs `run-49c4f5e97f2d41d6`, `run-57d16125a4a94de0` and `run-de1c989117414c1c` (2026-10-02), the `generate_options` input artifact had `request.findings: []` every time, right after the host submitted 6-11 findings in a `synthesize_evidence` step of the same decision.
- The decision keeps synthesis claims in `cont.findings` (loading.py `_keep_findings`), but the options request is built without them (requests.py `options_request`).

## Scope (no acceptance criteria by user decision)
- Locate where the options request payload is built, and pass the decision's kept findings (bounded) into `OptionsRequestPayload.findings`.
- Tests: after a synthesis outcome, the next options request carries its findings; with none kept, it stays empty.

## Comments
