---
title: "Product truth: the decision lifecycle, from forming to reuse as precedent (#DecisionLifecycleProductTruth)"
date: "2026-10-02"
time: "08:45"
type: feature
components: 
  - ux_prototyping
  - decision_kernel
summary: "The product-truth store now shows end to end how a Leafcutter decision is formed in a kernel run, staged as a record, published into docs/decisions and reused as precedent by a later run: one parent flow whose four steps expand into four sub-flows, a canonical Decision dataset built from the real records, and five screens for the human decision points and record views, all rendered in the Atlas."
description: "Modelled as decided through the kernel (dec-5e7445182eaec1f2, approved by the user): leafcutter/decision-lifecycle expands into decision-forming (11 steps; decision points approve-proposals and the ranked choice; branches for revision, re-ranking, no answer and the budget reserve), decision-staging (4 steps), decision-publishing (6 steps; publish or keep staged, exit-3 refusals, --correct) and decision-retrieval (5 steps; the 0.5 evidence and 0.8 reuse gates, reuse or decide anew). Hand-offs use produces/consumes (resolved decision, staged record, published record, index.json) with no broken link; actors are named per step; thresholds and exit codes were checked against the merged decision-store code. New entity Decision with the canonical dataset leafcutter/decisions (four real records plus two marked illustrative for supersession), and mockups decision-approve-proposals, decision-ranked-choice, decision-reuse-or-decide-anew, decision-record-staged and decision-record-published wired to their steps. Validator and generator check pass (0 errors); no acceptance criteria by user decision."
---

## Entry
