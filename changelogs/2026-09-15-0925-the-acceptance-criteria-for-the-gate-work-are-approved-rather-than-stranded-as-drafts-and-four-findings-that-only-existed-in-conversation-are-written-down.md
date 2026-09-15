---
title: "The acceptance criteria for the gate work are approved rather than stranded as drafts, and four findings that only existed in conversation are written down"
date: "2026-09-15"
time: "09:25"
type: manual
components: 
  - commit_guardian
  - guardrail_engine
summary: "Closes the bookkeeping left by GE-120h: seven acceptance criteria were stuck at readiness draft and therefore invisible as work, KI-TQ-007's status still described its remedy as unbuilt, three defects found during the work had never been filed, and the evidence report for the nine remaining scripts was sitting untracked. GE-120h-3 is deliberately left open, with a note recording which three of its five arms actually landed."
description: "The seven GE-120h records were authored by dispatching the PO, BA and IT PO agents directly rather than through the plan-feature workflow, so the final gate that sets readiness never ran and the criteria could not be picked up as ready work; they are approved at the priority the PO authored. GE-120h-3 is NOT marked done and a note now says why, because its bare status is readable two wrong ways: three arms landed — the five checks run on an ordinary commit and it completes, pre-existing directory density reports without refusing, and the record of unrun checks shrank by exactly those five — while two did not. The outstanding pair are the ones that matter most: no one of the five has been shown actually refusing an input it exists to refuse, so all five passing proves only that they do not crash; and a check with nothing to examine should say so rather than report a clean pass, which two of them currently do not. Three findings are filed: a hook registered on the post-merge stage renders correctly into the config but installs no git shim unless a ticket worktree was created, so a consumer has it registered and silent; a real-git test fixture can fail its own teardown while every assertion passes, costing a CI cycle and presenting as a defect in whatever change is on the branch; and the documentation-length check, newly flipped from warning to refusing against a three-hundred-line limit, now refuses any edit to the known-issues registers, which run to several thousand lines — it blocks the surface the project records defects on, and no CI check runs it, so the flip was invisible to every pull request."
commits: 
  - c7b9e40a2
breaking: false
---

## Entry
