---
title: "Wire the product-truth authoring phase into /plan-feature"
date: "2026-07-14"
time: "22:40"
type: feature
components: 
  - ux_prototyping
  - ac_store
  - build_pipeline
summary: "Added an always-on product-truth phase to /plan-feature: classify the request, draft the needed artifacts (mock-data, mockup, flow) behind gates and surgical commits, then derive ACs from the approved flow and reconcile step.implements back-links."
description: "Wires the four product-truth authoring agents (pt-classifier, mock-data-author, mockup-author, flow-author) into templates/workflows-js/plan-feature.js between ac-triage and the AC pipeline. The classifier runs on every invocation and the run-set is derived from its outcome via OUTCOME_TO_STAGES (never the advisory dispatch array); outcome=none and unparseable/inconsistent classifier output skip the phase. Artifact agents run in the fixed order mock-data->mockup->flow behind approve/edit/cancel gates, each committed surgically (reported paths + index.json only; docs/acceptance-criteria excluded) under subject plan-feature(<STAGE>): <component>, with commit-before-next, cancel-preserves-prior-commits, and a fail-closed main-branch refusal. The approved flow is committed before the business-analyst stage (forced in on the technical route with an L1 anchor), and apply_flow_backlinks.py reconciles the reported flow_backlinks into step.implements and re-runs the generator on its own commit. A non-silent store-absent self-skip lets the phase degrade loudly. AC store reconciled: new L1 UXP-595 with UXP-544-549 and UXP-595a; existing UXP-401/402/530 set to in_progress and UXP-543 to done with implemented_by/covered_by populated; both meta-flows impl_status regenerated. ADR-021 records the decision."
adrs: 
  - ADR-021-plan-feature-product-truth-phase
breaking: false
---

## Entry
