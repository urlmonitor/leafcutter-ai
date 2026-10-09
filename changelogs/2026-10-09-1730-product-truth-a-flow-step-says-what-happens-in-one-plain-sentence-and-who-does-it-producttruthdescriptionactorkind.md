---
title: "Product truth: a flow step says what happens in one plain sentence and who does it (#ProductTruthDescriptionActorKind)"
date: "2026-10-09"
time: "17:30"
type: manual
components: 
  - ux_prototyping
summary: "A flow step's human field is now description: one plain sentence of what happens, at most 200 characters, with no code paths, identifiers, ids or build status, enforced by the validator. A new actor_kind field says who does the step (deterministic code, Jev, an LLM or a person) and the Atlas shows it as a badge. Contract details are no longer pasted into the text; the Atlas renders them from io_contracts."
description: "Implements decision dec-7b1dcfd47f85cf0a. All 27 flows were migrated (304 nodes; the flow JSON shrank from 2.29 MB to 1.57 MB). The schema reference, authoring how-to and flow-author template carry the never-list; ACs UXP-523-3, UXP-523-4, UXP-700e-2-ii and UXP-542-1 were amended to the new rule."
---

## Entry
