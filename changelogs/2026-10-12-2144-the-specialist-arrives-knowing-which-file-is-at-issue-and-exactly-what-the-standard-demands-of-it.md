---
title: The specialist arrives knowing which file is at issue and exactly what the standard demands of it (BO-3800c)
date: "2026-10-12"
time: "21:44"
type: manual
components: 
  - build_orchestration
  - supervisor_system
  - commit_guardian
summary: "A complexity refusal now prints a machine-readable record of each refused function, and build-feature and build-ticket stop rather than engage the restructuring specialist when a refusal carries no usable demand."
description: "BO-3800c-1, -1-i, -2. check_complexity.py's refusal now also prints a COMPLEXITY_REFUSAL_RECORD line: a JSON list of {path, function, score, ceiling, reason}, one entry per refused function in refusal order. The specialist's demand is carried from that record, not re-derived from the human sentence. In both twin drivers (templates/workflows-js/build-feature.js and build-ticket.js) the engage-specialist handoff now checks that the demand is usable before engaging anyone. Every entry needs a non-empty path and either a function with a finite score and ceiling, or a positive lines_to_remove. If the demand is missing, empty or malformed, the run stops and reproduces the demand as given. Nobody is engaged, delivery is not retried, and the demand is no longer defaulted to an empty list. Both drivers were already over their size limit, so the change repays its lines by collapsing single-statement refusal guards onto one line and removing blank lines; no refusal text or logic changes. Tests: unit_tests/workflows/test_bo_3800c_1.py, test_bo_3800c_1_i.py, test_bo_3800c_2.py (shared _bo3800c_support.py). BO-3800c and its children are marked done."
breaking: false
---

## Entry
