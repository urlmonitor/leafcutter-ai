---
title: "Docs: the run-the-decision-kernel how-to says free text at the ranked choice is 'recorded only', but it re-ranks"
status: todo
components:
  - decision_kernel
created: 2026-10-02
depends_on: []
priority: medium
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: docs
risk_surface: internal
tags:
  - decision-kernel
  - documentation
  - acceptance-criteria
last_updated: 2026-10-02
agents:
  documentation-expert: needed
  commit: needed
---

# Docs: the run-the-decision-kernel how-to says free text at the ranked choice is 'recorded only', but it re-ranks

## Actor / Goal
In order for a person to know what happens when they answer the ranked choice in their own words, we need the how-to to say what the kernel does.

## Context
- **Found by:** the it-po verification pass for `DK-300b-2-ii`, ticket `TICKET-20261002-DecisionLifecycleACs`.
- **The inaccuracy:** `docs/how-to/run-the-decision-kernel.md` says a words answer at the ranked choice is "recorded only". It is recorded and also passed to Jev as constraints, which re-ranks: a second `decision.assess` call, a new ranked question, nothing selected. The words are never interpreted as a choice or a condition (`TICKET-20261002-KernelInterpretFreeText`).
- **A second contradiction:** `DK-300d-1` says Claude Code runs `decisions publish` at the person's request. The `/leafcutter` `SKILL.md` says publish is "the user's to run, never yours". The two stay inconsistent until `TICKET-20261002-KernelGatedDirectPublish` lands.
- **Related:** `DK-300b-4`, the how-to AC, must also say that `edited_criteria` replaces the whole proposed set.

## Scope (no ACs, by user decision)
- Correct the free-text paragraph in `docs/how-to/run-the-decision-kernel.md`: recorded, and re-ranks.
- Add the `edited_criteria` replacement rule from the `DK-300b-1-i` gap.
- Note the publish wording contradiction in the how-to's publish step, and point to `TICKET-20261002-KernelGatedDirectPublish`. Do not change the skill text here.

## Out of Scope
- Kernel code and the `SKILL.md` text.

## Comments
