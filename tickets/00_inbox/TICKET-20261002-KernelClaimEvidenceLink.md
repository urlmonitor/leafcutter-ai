---
title: "Kernel: evidence found for a human-added option is cited on it even below the relevance bar"
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
  - kernel/capabilities/research/collect.py
agents:
  test-writer: signed_off
  python-coder: signed_off
  commit: signed_off
---

# Kernel: evidence found for a human-added option is cited on it even below the relevance bar

## Actor / Goal
In order to judge an option a human adds on what research found about it, we need the evidence its claim search returned to be cited on that option, so the ranked question and the decision record no longer say "no evidence cited" when evidence exists.

## Context
- **Live reproduction:** run `run-de1c989117414c1c` (2026-10-02). The claim children for `need.claim.opt.added.1` and `need.claim.opt.added.2` returned 5 and 6 evidence items (`result-inv-2298bf71d093452a.json`, `result-inv-0f73cb6452fd4a4e.json`), but `need_evidence` is `{}` in both and in the research parent (`result-inv-9b00c50d71f54bf6.json`). The ranked question showed "Evidence: no evidence cited" for every human-added option.
- **Cause:** `kernel/capabilities/research/collect.py` `_absorb_bundle` records in `need_evidence` only items with `provenance.relevance >= bar` (0.7). Every claim item scored below the bar, so `passed` is empty, `results.py` drops the empty entry, and `kernel/capabilities/decision/loading.py` `_link_claim_evidence` has nothing to link to the option's `source_refs`.
- Jev's assessment already receives all evidence in one batch (`assess.py`), so the defect is the per-option citation (report, record, `Working.evidence_for` priority), not Jev's input.
- Filed as a ticket, not an AC: decision-kernel work carries no ACs by user decision (see `TICKET-20261001-KernelPrecedentSkipsGrounding.md`). Requested by the owner as a quick fix before re-running the decision-classifier decision.

## Scope (no acceptance criteria by user decision)
- For claim needs only (id prefix `CLAIM_NEED_PREFIX`, `need.claim.`), the evidence the single-need claim child returned is recorded in `need_evidence` even below the relevance bar; each item keeps its relevance on its provenance.
- Non-claim needs keep the relevance-gated behaviour; `_answer_checks` (SATISFIED needs only) is unaffected.
- Tests (test-first, red before the fix, mutation-proven): a single-need claim bundle with all items below the bar yields those ids in `need_evidence` for the claim need; a non-claim single-need bundle below the bar still yields none; end to end, `_link_claim_evidence` puts them on the option's `source_refs`. Tests live with the existing research collect and decision loading tests under `tests/kernel/`.

## Out of Scope
- How many claim needs are created per round (`research.max_targeted_needs`): `TICKET-20261002-KernelResearchEveryAddedOption.md`.

## Comments

### 2026-10-02 12:40 — test-writer (status: ok)
feedback-id: fb_2026-10-02_d3cd3362
tests/kernel/grounding/test_claim_evidence_below_bar.py: 3 tests. Red on the unfixed code: `test_claim_need_records_evidence_below_the_bar` and `test_collected_claim_evidence_links_to_the_human_added_option` failed on missing ids; the non-claim guard passed.

### 2026-10-02 12:41 — python-coder (status: ok)
feedback-id: fb_2026-10-02_e13109d4
`collect.py` `_absorb_bundle`: a claim need records every item its single-need child returned. The answer judgement still reads only items at or above the bar (`_passing_ids`, the same `retrieval.coverage_relevance_threshold` bar the collect path passes in). Verification:
- the new tests are green;
- mutation proof: with the fix reverted, 2 tests fail; with it restored, all 3 pass;
- the full `tests/kernel` suite: 1461 passed, 7 skipped;
- ruff is clean.

### 2026-10-02 13:00 — commit (status: ok)
feedback-id: fb_2026-10-02_3ac961be
Committing collect.py fix, new test, and ticket sign-offs; build-churn files left unstaged.

completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
