---
title: "spec: frontend code declares the acceptance criterion it renders (GE-124, UXP-611)"
date: "2026-08-24"
time: "18:05"
type: manual
components: 
  - ac_store
  - commit_guardian
  - precommit_hooks
  - frontend_coding
  - ux_prototyping
summary: "Authors the GE-124 acceptance-criterion family (57 records) specifying a commit-time and CI-time guardrail that makes frontend source declare the criterion it renders, plus UXP-611 (6 records) covering the design-side half, and the canonical product-truth dataset both are modelled on. Specification only -- no guardrail code is implemented by this change."
description: "GE-124 is the frontend sibling of GE-117 (Python-shaped code-to-AC declaration) and GE-111 (AC implemented_by drift). GE-117 is written entirely in Python vocabulary -- module docstring, public function or class, __all__ -- and reaches no .tsx/.jsx/.vue/.svelte/HTML file, so frontend source had no path back to the requirement it satisfies while frontend tests already did via // covers: tags. Two declaration surfaces: a component-level declaration in each frontend component file (the required floor) and an optional element-level data-ac attribute pinning one rendered element to one criterion. A data attribute rather than a CSS class because class is the styling namespace and is purged or hashed by Tailwind content scanning and CSS modules, whereas a data attribute is inert, greppable and survives minification. Enforcement is diff-scoped on both tiers, matching check_done_proof --mode ci-changed: commit tier validates staged frontend files forward; CI tier evaluates only criteria the change touched, entering evaluation either by the record appearing in the diff or by a changed frontend file declaring or pinning it. There is no cutoff date, exemption list or backfill backlog -- coverage grows as files are touched. GE-124g is the load-bearing safety property: a declaration is on-screen-presence evidence and never coverage evidence, blocked at four independently testable points (the store, the done gate, reports, and the test selector), with no warn tier and no opt-out. UXP-611 covers the half GE-124 cannot reach: mockup-author emitting the same data-ac grammar into rendered mockup HTML, so mockup-versus-built becomes a mechanical diff and the realization built/spec/mock axis becomes evidenced rather than self-declared. All 63 records are readiness: approved, priority: high (GE-124) and readiness: draft, priority: medium (UXP-611), and every GE-124 leaf carries a test contract that survives promotion under validate_test_contract."
breaking: false
---

## Entry
