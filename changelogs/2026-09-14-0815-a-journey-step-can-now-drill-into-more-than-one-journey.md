---
title: "A journey step can now drill into more than one journey, and a branch can say what kind of outcome it is"
date: "2026-09-14"
time: "08:15"
type: manual
components: 
  - ux_prototyping
summary: "A step's expands_to is now a list of child journeys. The older single-id shape is still read, and the generator writes it back as a list. Branches gain an optional outcome_kind, reported as a field to fill while it is introduced."
description: "Two fields in the journey shape change without a flag-day migration (UXP-700e-3-i). A step's expands_to was one child-journey id; it is now a list, so a step can drill into several journeys. Every reader -- the generator's status rollup, the parent/child hierarchy, the cycle and dangling-reference checks, and the web explorer -- accepts both the single id and the list, and the generator writes only the list. This commit regenerates the three journeys that used the single-id shape (customer-buys-a-plant, deliver-a-feature, how-acs-are-built); their derived statuses are unchanged. A step expanding into several journeys is done when all of them are done, not started when none has started, and in progress otherwise. Branches gain an optional outcome_kind: alternative, failure or exit. No journey carries one yet, so the checker reports each journey's unfilled branches as a [to-be-filled] warning, never as an error. The web explorer drills into the first child when a step lists several."
commits: 
breaking: false
---

## Entry
