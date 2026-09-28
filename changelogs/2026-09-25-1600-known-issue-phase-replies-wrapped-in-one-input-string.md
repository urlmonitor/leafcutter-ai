---
title: "Known issue recorded: phase replies wrapped in a single input string halt the drive"
date: "2026-09-25"
time: "16:00"
type: manual
components:
  - build_orchestration
summary: "Records KI-BO-20260925-1309: phase agents that pass their result as one JSON string inside an `input` field, and a reply schema whose error then sent every retry after the wrong field, halted three epic drives with their work already done."
description: "On 2026-09-25 three /build-feature drives against EPIC-TruthfulProjectRecord halted at the five-retry cap on a phase agent's reply. documentation-expert, and once ac-fulfillment-gate, had passed the phase result as a JSON string inside a single `input` field instead of filling the reply tool's fields; the deliverables were on disk each time and the tickets were closed by hand. The new entry docs/known-issues/build-orchestration/open-blocker-ki-bo-20260925-1309.md records the exact reply sent and two compounding causes: the 36 agent templates whose output contract asks for 'exactly one JSON value', which conflicts with the tool-field schema the driver enforces, and the schema's handoff conditional, which passed when status was absent and so pointed every retry at handoff_target. It links KI-BO-20260901-1045, whose remaining scope names the same two agents, and notes that the error observed here shows the engine does enforce the schema's if/then. Mitigated by #902 (BO-3000b) and #903 (BO-2000c-5); it stays open until the reply contract is stated once and the templates reconciled. The build-orchestration index gains the row, and its header counts are corrected to the files on disk (51 open, 15 resolved)."
commits:
breaking: false
---

## Entry

A new known issue, KI-BO-20260925-1309, records why three epic drives halted today: phase
agents wrapped their reply in a single `input` string, and the reply schema's error sent
every retry after the wrong field. Two fixes that mitigate it are already merged; the entry
stays open until the agent templates and the enforced reply shape agree.
