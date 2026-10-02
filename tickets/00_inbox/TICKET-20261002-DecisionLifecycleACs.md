---
title: "ACs for the decision lifecycle, so the Atlas shows its real implementation status"
status: in_progress
components:
  - decision_kernel
  - ux_prototyping
created: 2026-10-02
depends_on: []
priority: high
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: docs
risk_surface: internal
tags:
  - acceptance-criteria
  - product-truth
  - decision-kernel
last_updated: 2026-10-02
agents:
  product-owner: signed_off
  business-analyst: signed_off
  it-po: signed_off
  python-coder: signed_off
  commit: needed
---

# ACs for the decision lifecycle, so the Atlas shows its real implementation status

## Actor / Goal
In order for the Atlas to show the decision-lifecycle flows' real state instead of "NOT STARTED", we need acceptance criteria derived from the flows' steps. The built ones are marked done with evidence (`implemented_by`, `covered_by`), and each step links its ACs through `implements`.

## Context
- **User decision (2026-10-02):** "atlas -> ACs".
- **The problem:** the flows (PR #980) show NOT STARTED because `impl_status` is derived only from the `work_status` of the ACs in each step's `implements`. The kernel work had no ACs: the user decided no ACs for the kernel build.
- **The decision-kernel flows:** `docs/product-truth/flows/leafcutter/decision-{lifecycle,forming,staging,publishing,retrieval}.flow.json` (30 steps, 12 branches, 42 acceptance scenarios).
- **How this is done here** (kernel run `run-0ee037dcf49c4a66`):
  - ADR-023: ACs are derived from flow steps.
  - A new namespace goes in `docs/acceptance-criteria/index.yaml`, with a kebab id and a 2–6 letter prefix.
  - The anti-phantom-done gate: a done AC referenced by a built flow needs `implemented_by` (leaf) or `covered_by` (composite).
  - KI-ACS-004 records ACs marked done with no code link. Avoid exactly that.
- **What is built** (merged on main: #973, #977, #978, #982):
  - forming: the decision capability, research, retrieval, Jev, and the human questions;
  - staging: `kernel/memory/staging.py` and `builder.py`;
  - publishing: `kernel/memory/publish.py` and the `decisions` CLI;
  - retrieval: `kernel/memory/precedent.py`, the `file_store` index lookup, and the reuse question.
  - Tests live under `tests/kernel/`.
- **Not built yet:** gated direct publishing (`TICKET-20261002-KernelGatedDirectPublish`). Steps or branches about direct publishing, if any, stay not done.

## Scope
1. **AC namespace** for the decision kernel in `docs/acceptance-criteria/index.yaml`.
2. **L0/L1** (product-owner), then **L2/L3** (business-analyst) derived from the flows' acceptance scenarios, then technical enrichment (it-po).
3. **Built ACs marked done with real evidence:** `implemented_by` names a file plus symbol in `kernel/...`, and `covered_by` names a test in `tests/kernel/...`. Every pointer must resolve, and nothing is marked done without evidence.
4. **Flows:** each step's `implements` lists its ACs. Run `generate_product_truth.py`; the validator passes, and the Atlas shows the true status.

## Out of Scope
- Kernel code changes.

## Sign-offs

- [x] product-owner — 2026-10-02 13:45
- [x] business-analyst — 2026-10-02 14:20
- [x] it-po — 2026-10-02 14:55
- [x] python-coder — 2026-10-02 15:33
- [ ] commit

## Comments

### 2026-10-02 15:33 — python-coder (status: ok)
feedback-id: fb_2026-10-02_e5ac0d41
Marked the decision-kernel ACs with their true status and wired them into the flows (nothing committed).
- **done (18):** DK-300a-1, a-2-i, a-2, a-4-i, a-4, b-1-ii, b-2-i, b-3, c-1-i, c-1, d-2-i, d-3-i, d-3, e-1, e-2-i, e-3-iii, e-3-iv, e-4. Each has `implemented_by` (it-po pointers) and `covered_by` (test pointers), `# covers: <id>` tags on the 104 cited existing tests (comment-only, 28 files in tests/kernel/), all cited tests run green, and `mark_ac_done.py --test-root tests` accepted each.
- **in_progress (30) / todo (6):** gaps are in each AC's notes; the L1s and the L0 are in_progress (derived from their children).
- **Deviation from the 22 built_and_tested:** DK-300b-1, b-2, d-2 and e-3 are L2 composites whose own tests pass and are tagged, but `check-done-proof` refuses a done composite with a child that is not done. They were marked done, then reverted to in_progress; they flip to done once their L3 children are done.
- **Flows:** `implements` filled on all 30 steps and 12 branches; generator write, `--check` and validator pass.
- **BA questions:** Q1 (hash mismatch skips with a warning) noted in DK-300e-1; Q2 (only options supplied with the task count) in DK-300e-3-iv; Q3 (journey steps link L2s) in DK-300.
- **Follow-up tickets:** KernelSynthesisCitationCheck, KernelSupersedePublishCorrect, DecisionKernelACTestGaps, RunKernelHowToFreeTextReRank. KernelPrecedentSkipsGrounding set to done.

