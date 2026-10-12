---
title: "Bind an explicit typed research root after eligibility checks"
date: "2026-10-02"
time: "17:01"
type: fix
components:
  - decision_kernel
summary: "A validated research request with evidence output reaches its unique eligible capability without a redundant semantic capability judgment."
description: "Fixes the typed research routing stop while preserving authorization, multiple-candidate choices, child routing, untyped intent classification and downstream Jev research decisions."
---

A root request with `leafcutter.research_request.v1` input and
`leafcutter.evidence_bundle.v1` output already fixes the answer contract. After the
existing eligibility checks, the scheduler binds its unique eligible capability
without asking Jev to classify the same capability again. Output-only requests,
other typed pairs, multiple eligible candidates and child requests keep their
existing routing. No confidence threshold changes.

The public-service regression reaches actual native ADR evidence and still runs
Jev research planning, relevance and sufficiency checks. The new tests also keep
permission, availability, binding and scope exclusions effective. A question
without a typed payload still invokes the intent classifier and asks for
clarification when confidence is insufficient.

The local compatibility selection passes **136 tests and 12 subtests** in 50.30s.
Three intentional wrong versions are rejected: removed binding, a shortcut for
all explicit outputs, and a binding that leaks to children. Source bytes were
restored exactly after those checks. See the [validation record](../reports/typed-research-binding-2026-10-02.json).

This is the bounded routing repair under KM-500a-2/KM-500d-1. Model answers in
these tests are scripted. It does not establish live Jev answer quality or full
RS-02/RS-03 completion, and no acceptance-criterion status is promoted.

After updating to merged main `d641028c`, the routing and changelog fidelity
selection passes **156 tests and 12 subtests** in 55.04s. The independent
configured-store census is 551 changelogs: main's 550 plus this record. Only the
two exact count sentinels change; source-set, metadata, roundtrip and all three
malformed-input recovery assertions remain intact. The initial receipts above
remain attributed to their earlier base.
