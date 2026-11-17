---
title: "A complexity refusal in a build brings in the restructuring specialist with the declared skill (BO-3800b)"
date: "2026-10-13"
time: "00:30"
type: manual
components: 
  - build_orchestration
  - commit_guardian
summary: "When a phase hands off because a check refused the commit and that check declares engage-specialist, build-feature and build-ticket now engage the declared specialist, not the coder that wrote the change, and tell it the demand and the skill to apply."
description: "BO-3800b-1, -2, -3. In both twin drivers (templates/workflows-js/build-feature.js and build-ticket.js) the handoff path now reads a phase result's remedy: when its disposition is engage-specialist, the driver reads that hook's remedy declaration through the shared loader (_remedy_declarations.load, GE-132a-1) and refuses, engaging nobody, unless the declaration reads as engage-specialist naming exactly the handoff target. It then carries a brief (the refusal's demand plus the declaration's skills, e.g. complexity-reduction) into the specialist's dispatch prompt and options. A refusal-triggered handoff to the declared specialist is honoured even when that agent is not in the ticket's agents map (the narrow BO-3000a exception); every other handoff keeps BO-3000a's existing refusals. Only engage-specialist engages anyone, so author-clears and mechanical-autofix refusals behave as before. The two drivers were already over their size limit, so the change repays its added lines two-for-one by collapsing single-statement refusal guards onto one line; no other behaviour changes. Tests: unit_tests/workflows/test_bo_3800b_1.py, _2.py, _3.py (shared _bo3800b_support.py) drive the real workflow bodies; harness_build_ticket_guard.mjs gains the remedy plumbing. BO-3800b-1, -2 and -3 marked done."
commits: []
breaking: false
---

## Entry
