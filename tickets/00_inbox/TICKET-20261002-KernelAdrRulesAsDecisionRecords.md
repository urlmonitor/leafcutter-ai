---
title: "Kernel: the rules of an accepted ADR can be filed as individual decision records"
status: todo
components:
  - decision_kernel
created: 2026-10-02
depends_on:
  - TICKET-20261002-KernelDecisionAudienceClassifier.md
priority: medium
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - decision-kernel
  - decision-store
last_updated: 2026-10-02
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Kernel: the rules of an accepted ADR can be filed as individual decision records

## Actor / Goal
In order that each rule an owner has already accepted in an ADR can be matched and reused as precedent on its own, we need a way to file those rules as individual decision records, each citing the ADR, without re-deciding them in a kernel run.

## Context
- **Owner decision, 2026-10-02:** the five rules of ADR-066 (accepted 2026-10-02) should be filed as separate decision records, with ADR-066 kept as their rationale. The owner chose to fold this into the audience-classifier work ("Fold into B"), so records are filed once, with an audience.
- Today a record can only be created inside a kernel decision run: the human chooses in the run, then runs `decisions publish`. Precedent matching works per record and per question, so five rules inside one ADR are one document, not five reusable precedents.
- ADR-060: only a human approval creates a record. The ADR's acceptance by its owner is that approval, and the record must point at it (the ADR, its acceptance commit, the approver).

## Scope (no acceptance criteria by user decision)
- A `decisions` CLI path (e.g. `decisions import-adr <ADR file> --rule <§n>`) that stages one record per accepted ADR rule:
  - question and selected option are taken from the rule;
  - rationale and evidence point at the ADR section;
  - `approval` cites the ADR acceptance (approver, commit, date) as an approval recorded outside the record;
  - `audience` is set per the audience-classifier ticket.
  The existing publish then writes it after `decisions validate`.
- It refuses ADRs whose status is not Accepted, and a rule already filed.
- Then file ADR-066's five rules this way.
- Tests:
  - an accepted ADR rule stages a valid record citing the ADR;
  - a proposed ADR is refused;
  - a duplicate is refused;
  - the staged record passes `decisions validate`.

## Comments
