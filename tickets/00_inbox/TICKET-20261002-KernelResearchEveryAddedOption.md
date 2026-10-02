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
  test-writer: signed_off
  python-coder: signed_off
  pr-reviewer: signed_off
  commit: signed_off
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

### 2026-10-02 14:50 — test-writer (status: ok)
feedback-id: fb_2026-10-02_c85d48d1
tests/kernel/grounding/test_claim_needs_cap.py: 3 tests, all red on the unfixed code. Only 2 of 21 human-added options got a claim need, `research.max_claim_needs` did not exist, and no limitation named the left-out options.

### 2026-10-02 15:00 — python-coder (status: ok)
feedback-id: fb_2026-10-02_c1540c2b

Added `research.max_claim_needs` (25) to ResearchConfig, default JSON and schema. `targeted()` now takes a claim limit and a gap limit; `max_targeted_needs` (2) caps gaps only. `claims_left_out` / `claim_limitations` name each human-added option the claim cap drops ("option opt.added.N was not researched: claim cap 25 reached"); the executor `_plan` puts them in the continuation limitations beside the `afford_needs` trims. `targeted_need_count` counts claims and gaps with their own caps. Updated two tests that encoded the shared cap (test_research_targeting default-cap test, test_round6_end_to_end bounded-round test): they now expect one claim plus two gaps.

### 2026-10-02 15:20 — pr-reviewer (status: ok)
feedback-id: fb_2026-10-02_badf6594

No high-confidence findings. Verified: `targeted()` has one call site (planning.py `_targeted`), updated; `targeted_need_count` (claims and gaps each capped) matches the needs `plan_needs` builds, and `afford_needs` trims from the tail (gaps first) so both stay consistent; the schema requires `max_claim_needs` but loading deep-merges overrides onto defaults (override lacking the key loads, value 25) and the schema file matches `render_config_schema()`; the two adjusted tests change only because the ticket redefines `max_targeted_needs` as gap-only (the gap-cap test is intact and the claim cap is covered by test_claim_needs_cap.py), so no contract shrinks. 30 targeted tests pass. Low-confidence nits (suppressed): test name `test_the_default_caps_targeted_needs_at_two` is now misleading; docs/how-to/run-the-decision-kernel.md:132 still describes `max_targeted_needs` as the shared cap.

### 2026-10-02 16:00 — commit (status: ok)
feedback-id: fb_2026-10-02_439630db

Auto-authorized commit gate: subject "fix(kernel): every human-added option gets its own claim research, under its own cap (#KernelResearchEveryAddedOption)"; 12 staged files (config, kernel, tests, how-to, ticket).
