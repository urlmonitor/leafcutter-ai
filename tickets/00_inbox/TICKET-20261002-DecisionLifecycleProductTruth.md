---
title: "Product truth: the decision lifecycle (formed, staged, published, retrieved)"
status: in_progress
components:
  - ux_prototyping
  - decision_kernel
created: 2026-10-02
depends_on: []
priority: high
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: docs
risk_surface: internal
tags:
  - product-truth
  - decision-kernel
last_updated: 2026-10-02
agents:
  pt-classifier: needed
  mock-data-author: needed
  mockup-author: needed
  flow-author: needed
  commit: needed
---

# Product truth: the decision lifecycle (formed, staged, published, retrieved)

## Actor / Goal
In order to review in the Atlas how a Leafcutter decision is formed, staged as a record, published into `docs/decisions/`, and retrieved as precedent by a later run, we need the decision lifecycle authored as product truth.

## Context
- **User request (2026-10-02):** a complete product-truth flow of how decisions are formed, saved, stored and retrieved, each stage probably its own product truth. It must be viewable in the Atlas (`leafcutter-web/`), or as an HTML file if the Atlas does not run.
- **Model, decided through the kernel:** decision `dec-5e7445182eaec1f2`, run `run-7c7d6474612b438b`, approved by the user. It chose one decision-lifecycle flow whose steps expand (`expands_to`) into four sub-flows, one per stage.
- **Ranking:** the kernel ranked "one flow with explicit decision points" first, "parent plus four sub-flows" second and "four separate flows" third. The user chose the second.
- **How each stage works (decision store, PR #978):**
  - **Forming:** a kernel run researches, Jev assesses, and a human approves the criteria and makes the ranked choice.
  - **Staging:** automatic. A resolved, human-approved decision is written to `<run_root>/runs/<run_id>/staged/decisions/<id>.yaml`.
  - **Publishing:** a human runs `python -m kernel decisions publish --run-id R`. It validates, writes `docs/decisions/<id>.yaml`, regenerates `index.json`, and then goes through normal git review.
  - **Retrieval:** a later decision's precedent node finds matching records through the index. Jev judges applicability: at 0.5 or above the record becomes evidence; at 0.8 or above you are asked to reuse it or decide anew.
- **Schema in use:** step `agent` (who acts), `produces`/`consumes` (the hand-offs: the staged record, then the published record and index), and `expands_to` (the sub-flows).

## Scope (no acceptance criteria, by user decision)
- A parent flow `leafcutter/decision-lifecycle` with four steps, each with `expands_to` set to its sub-flow.
- Four sub-flows:
  - forming a decision;
  - staging the record;
  - publishing the record;
  - retrieving a precedent.

  Each names its actors and hand-offs, and shows the human decision points: approving the criteria, the ranked choice, running publish, and reuse or decide anew.
- Mock data and mockups as the classifier decides, following the add-vs-create protocol. Mock data is built from the real records (`dec-ef8ddcb79d668a67` and the staged ones).
- `docs/product-truth/scripts/validate_product_truth.py` and `generate_product_truth.py --check` pass.
- The flows render in the Atlas, or else in a standalone HTML review page.

## Out of Scope
- Acceptance criteria and `implements` links: no ACs, by user decision.
- Kernel code changes.

## Comments
