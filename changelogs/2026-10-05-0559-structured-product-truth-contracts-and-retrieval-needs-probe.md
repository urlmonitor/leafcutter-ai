---
title: "Structured Product Truth contracts and retrieval-needs probe"
date: "2026-10-05"
time: "05:59"
type: manual
components:
  - ux_prototyping
  - decision_kernel
summary: "Documented and enforced flow JSON contracts, made Atlas contract details readable, and preserved an isolated retrieval-needs experiment."
description: "Migrated all 26 Product Truth flows to explicit contract fields/examples or honest non-JSON and proposed binding gaps; added automatic pre-commit and CI validation and readable Atlas field tables with separate raw JSON examples. Added acceptance criteria and regression coverage. Included the isolated kernel host retrieval-needs interpreter and its frozen evaluation evidence: 12/12 host completions and 8/12 minimum semantic checks, without production retrieval integration or a trained classifier claim."
---

The declared missing bindings remain planning work. Saved semantic evaluations are historical evidence, not new evaluations of the merged release. The upstream entity-context behavior is retained when integrating main.

Release checks also exposed an artifact-evaluation dependency gap and failed model invocations being counted as valid all-false labels. The evaluation repair copies bounded declared dependencies, checks the target contract independently of unrelated baseline errors, and records missing model outputs as failures without changing score thresholds. Atlas production-build lint and changed-file Python typing findings were corrected.

Composite proof-of-done verification now uses the existing Python and TypeScript runners for its covered children. Every child still needs passing proof; missing coverage, incomplete runs, unavailable JavaScript runners and actual failed assertions remain blocking. The helper is included in normal consumer deployment.
