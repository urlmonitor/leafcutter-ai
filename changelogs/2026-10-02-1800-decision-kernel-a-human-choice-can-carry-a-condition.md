---
title: "Decision kernel: a human choice can carry a condition, and a choice at an escalation resolves"
date: "2026-10-02"
time: "18:00"
type: manual
components: 
  - decision_kernel
summary: "When the kernel asks you to choose, you can pick an option and add a condition in the same answer, and picking an option when the kernel escalates now settles the decision."
description: "leafcutter.human_answer.v1 accepts the pair {choice_id, free_text} wherever free text is allowed. The choice is authoritative, and the text is kept verbatim as a condition: it reaches Jev's constraints labelled human-stated, the decision rationale, and the staged record's task_context.constraints. Choosing a usable option at an escalation (tie, conflict, preference, unidentified gap) now resolves the decision with the human as approver and design_reason human_ruling, instead of looping. The Claude Code and Codex skills tell the host it may send the pair. Other mixed modes stay rejected. TICKET-20261002-KernelChoiceWithCondition."
commits: 
  - 03c4b7bb3e79d36b911f54ecb3f7bf468cff2155
---

## Entry
