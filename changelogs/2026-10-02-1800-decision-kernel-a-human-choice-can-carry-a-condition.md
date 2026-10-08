---
title: "Decision kernel: a human choice can carry a condition, and a choice at an escalation resolves"
date: "2026-10-02"
time: "18:00"
type: manual
components: 
  - decision_kernel
summary: "When the kernel asks you to choose, you can pick an option and add a condition in the same answer, and picking an option when the kernel escalates now settles the decision."
description: "leafcutter.human_answer.v1 accepts the pair {choice_id, free_text} wherever free text is allowed (the proposals approval, the ranked design choice and an escalation); the decision-approval and precedent questions still reject it. The choice is authoritative and the text is kept verbatim as a condition: it reaches Jev's constraints labelled human-stated, every rationale written afterwards (one 'Condition stated by the human: <text>' per condition, via one condition_suffix helper, on the ranked-choice, human-ruling, gate-resolved and precedent-reuse rationales) and the staged record's task_context.constraints. An unusable or unrecognised choice keeps no condition. Choosing a usable option at an escalation (tie, conflict, preference, uncertain) now resolves the decision as a human ruling (design_reason human_ruling; limitation 'human ruling: <approver> chose [<id>] at a <reason> escalation') instead of only recording a preference. The Claude Code and Codex skills tell the host it may send the pair. Product truth: the decision-forming flow gains an escalation-ruling branch and documents the pair, the decisions dataset gains conditions and rationale_suffix, and the decision-ranked-choice and decision-record-published mockups show the condition. TICKET-20261002-KernelChoiceWithCondition."
commits: 
  - 03c4b7bb3e79d36b911f54ecb3f7bf468cff2155
---

## Entry
