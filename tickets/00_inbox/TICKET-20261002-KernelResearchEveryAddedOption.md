---
title: "Kernel: every option a human adds gets its own claim research, under its own cap"
status: todo
components:
  - decision_kernel
created: 2026-10-02
depends_on: []
priority: high
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - decision-kernel
  - decision-basis
last_updated: 2026-10-02
files_touched:
  - kernel/capabilities/research/targeting.py
  - kernel/config.py
  - config/kernel_config.default.json
  - config/kernel_config.schema.json
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
---

# Kernel: every option a human adds gets its own claim research, under its own cap

## Actor / Goal
In order to decide on a proper evidence basis when the owner adds options, we need each human-added option to get its own claim search, so no option is ranked on evidence nobody looked for.

## Context
- **Live reproduction:** run `run-de1c989117414c1c` (2026-10-02). The owner added 21 options (classifier dimensions). Only `need.claim.opt.added.1` and `need.claim.opt.added.2` were created; the other 19 options were never researched and were still ranked.
- **Cause:** `kernel/capabilities/research/targeting.py` `targeted()` returns "human-added option claims first, then named gaps, at most `limit`", and `limit` is `research.max_targeted_needs` = 2 (`config/kernel_config.default.json`). Claims and gaps share one small cap.
- Related: ADR-066 §2 (an option with no relevant evidence is reported as unresearched, not scored). Filed as a ticket, not an AC (decision-kernel work carries no ACs by user decision).

## Scope (no acceptance criteria by user decision)
- Claim needs get their own config key (e.g. `research.max_claim_needs`), separate from the gap-need cap, with a default high enough that a typical human addition is fully researched; the existing gap cap is unchanged.
- Every human-added option the claim cap leaves out is named in the run's limitations ("option X was not researched: claim cap N reached").
- Config model, default JSON and schema are updated together; the config tests cover the new key.
- Tests: with 21 human-added options and the default cap, every option gets a claim need; with a cap below the count, the excess options are named in the limitations; gap needs still follow their own cap.

## Comments
