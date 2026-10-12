---
title: "Kernel: options a human adds are researched and cite their evidence; nine dogfood tickets filed"
date: "2026-10-02"
time: "16:15"
type: fix
components:
  - decision_kernel
summary: "Every option a human adds to a kernel decision now gets its own claim search, under a separate cap of 25, and the evidence that search finds is cited on the option even when it scores below the relevance bar. Nine decision-kernel tickets from the 2026-10-02 dogfood runs are filed."
description: "Before, research.max_targeted_needs (2) capped claims and gaps together, so only 2 of 21 human-added options were researched, and claim evidence below the 0.7 relevance bar was never linked, so options read 'no evidence cited'. research.max_claim_needs (25) now caps claims and max_targeted_needs caps gaps only; options the cap leaves out are named in the limitations. The answer judgement still reads only evidence at or above the bar."
---

## Entry

A decision now researches every option a human adds, up to `research.max_claim_needs` (25),
separately from synthesis gaps (`research.max_targeted_needs`, 2). Options the claim cap leaves
out, and needs the Jev-call budget trims, are named in the run's limitations.

Evidence a claim search returns is cited on the option it checked even below the relevance
bar, so the ranked question and the decision record show what each option rests on. Whether
a need is answered is still judged only on evidence at or above the bar.

Nine standalone decision-kernel tickets record the defects found while dogfooding the kernel on
2026-10-02 (research before a blind escalation, apply each human answer once, a choice with a
condition, LLM interpretation of free text, findings reaching option generation, a run store
independent of the current directory, a runnable publish command, and the two fixes above).
