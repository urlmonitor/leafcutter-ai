---
title: "Traceability guardrails explainer, and the in-flight known-issues work renumbered onto current main"
date: "2026-08-25"
time: "09:30"
type: manual
components: 
  - documentation_system
  - build_pipeline
  - commit_guardian
summary: "Adds an explainer mapping which AC/code/test/doc/flow links are enforced mechanically versus only by agents, and lands four known-issues changes that had been authored against a stale main."
description: "Adds docs/explanation/traceability-guardrails.md, which answers a single question: if nobody runs a workflow and no agent is dispatched, what still forces the links between an acceptance criterion, its code, its test, its documentation and its product-truth flow to exist and stay correct? The answer it documents is that AC-to-Tests and AC-to-Flows are mechanically enforced while AC-to-Code and AC-to-Docs are authored by agents and verified only by agents. It also notes that flow.schema.json types every flow as user, data or architecture, and that the AC-linking machinery is identical across all three. Alongside it, four known-issues changes that had been sitting uncommitted on a local main seven commits behind origin are rebased onto current main. KI-DS-001 gains a consumer-install occurrence recording that the Diataxis specialists have since split on failure posture — reference-author and explanation-author now hard-stop on the missing convention while how-to-author and adr-author leave it unstated — and that write-reference.md exists only as package documentation, so no build phase ships any convention to an adopter. KI-CG-008 is filed: validate_paths checks that related_docs is a list but never that its elements are strings, so a labelled entry raises TypeError rather than emitting a validation error, and at least 33 of 50 documents in the reporting install use that form. The adopter-skills defect is filed as KI-BP-009 rather than the KI-BP-008 it was authored as, because origin/main had meanwhile shipped a different KI-BP-008 — the number was free when written and taken by the time it landed. KI-BP-003 goes to three occurrences, with the third report's claim that the crash also fires on main left explicitly unresolved against the second report's contrary evidence, accompanied by the one-line ancestor-walk probe that settles it. A gutted docs/INDEX.md found in the same tree was discarded rather than committed: every section had been replaced with 'No docs found', which is KI-BP-001 firing rather than authored work."
commits: 
  - 2e5b79b8
  - 5fde9e39
  - 6b09bf85
breaking: false
---

## Entry
