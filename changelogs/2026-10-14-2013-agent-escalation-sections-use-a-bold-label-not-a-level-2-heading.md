---
title: "Agent escalation sections use a bold label, not a level-2 heading"
date: "2026-10-14"
time: "20:13"
type: manual
components: 
  - agent_registry
  - build_orchestration
summary: "Agents that report an escalation now write it as a bold label instead of a section heading, so their ticket comments can no longer be misread as starting a new section."
description: "Commit cbb15019c (AC BO-400a-2-vi). The architect-review, conflict-resolver and pr-reviewer agent templates and the pr-review workflow description now instruct a bold **Escalation** label line in the agent output instead of a level-2 ## Escalation heading; the Branch and Reason lines and the templates' own section headings are unchanged. That output lands in a ticket's ## Comments, where a level-2 heading read as a section boundary and on 2026-09-30 a newer gate entry was written above an older ok for the same gate (KI-BO-20261009, mechanism 1). KI-BO-20261009 is downgraded from blocker to low: mostly fixed by BO-400a-2-v (PR #1201) and this change; still open is that the latest sign-off entry is taken to be the last one in file order. Adds unit_tests/agents/test_bo_400a_2_vi.py. docs/INDEX.md carries a 4-line re-sort produced by the doc-index transform hook."
commits: 
  - cbb15019c
breaking: false
---

## Entry
