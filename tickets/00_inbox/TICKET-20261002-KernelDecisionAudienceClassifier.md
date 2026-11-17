---
title: "Kernel: decision records carry an audience (leafcutter_only / customer / both) assigned by Jev under a user-set threshold"
status: todo
components:
  - decision_kernel
created: 2026-10-02
depends_on: []
priority: high
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: true
change_target: code
risk_surface: contract_boundary
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

# Kernel: decision records carry an audience (leafcutter_only / customer / both) assigned by Jev under a user-set threshold

## Actor / Goal
In order that decisions which bind customers' projects are kept apart from decisions that only govern Leafcutter itself, we need every decision record to carry an audience: Jev assigns it from described criteria, and the owner decides only when Jev is below a threshold the user can set.

## Context
- **Owner decision, 2026-10-02:** kernel run `run-35ecc5ce9780442d`, staged record `dec-e4c6a3e133b9694b`. The owner chose "One audience classifier (leafcutter_only / customer / both), chosen by Jev from described candidates, with a user-set, risk-specific human-in-the-loop threshold" over a classifier framework, audience + binding, no new classifier, and 21 other dimensions they had proposed.
  - Their wording: "make it so that I only decide if it is <90%. and I would think this would be a nice setting that users should be able to set. a human in loop threshold".
  - Example: how to fill product truth is `both`.
- **Constraints the research surfaced:**
  - **ADR-061 §4:** record filters must use a vocabulary already defined elsewhere, and `decisions validate` rejects any other value. Audience therefore needs a home vocabulary first, or an ADR-061 amendment. Candidates already in the repo:
    - AC `package_surface: true` (ACS-100i-6);
    - the build's ownership predicate `package_produced` / `adopter_owned` (`scripts/build_ownership.py`);
    - components described as "not shipped to adopters".
  - **Ownership rule** (`docs/reference/example-content-separation.md`, ADR-044): product membership is decided by location or id, never by content. This is in tension with Jev judging audience from the text; the ADR must address it.
  - **Spec rev3 §9.4:** thresholds are configurable and risk-specific, calibrated on representative cases, and never read as "90% probability of being right".
  - **ADR-060:** a Jev label never carries approval authority; a record still needs a human approval.

## Scope (no acceptance criteria by user decision)
- ADR (dispatch `adr-author` directly with a pinned number):
  - the audience vocabulary and where it lives (ADR-061 §4);
  - how it relates to the ownership rule;
  - the threshold semantics: which number (winning probability vs confidence), and that the threshold is per classifier.
- Record field `audience`, plus provenance: assigned by Jev with its probability, or by the human.
- Jev assigns it at staging from fixed, described candidates (with a needs-context candidate):
  - at or above `memory.audience_threshold` (default 0.9, user-settable in config), the label is applied and recorded as Jev's;
  - below it, the human is asked as part of the approval.
- Precedent lookup in a customer's project offers only `customer` and `both` records; in leafcutter-ai all records apply.
- Tests:
  - the label is applied above the threshold and asked below it;
  - provenance is recorded;
  - `decisions validate` accepts only the declared vocabulary;
  - the precedent filter honours the audience in a customer install.

## Comments
