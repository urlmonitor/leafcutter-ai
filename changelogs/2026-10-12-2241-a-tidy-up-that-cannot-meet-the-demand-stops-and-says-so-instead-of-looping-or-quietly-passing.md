---
title: "A tidy-up that cannot meet the demand stops and says so, instead of looping or quietly passing (BO-3800d)"
date: "2026-10-12"
time: "22:41"
type: manual
components: 
  - build_orchestration
  - supervisor_system
  - commit_guardian
summary: "build-feature and build-ticket now engage the restructuring specialist at most once per delivery. A refusal that still stands afterwards, or a specialist that fails, stops the run with an account of what was asked and where the file stands."
description: "BO-3800d-1, -2, -3. In both twin drivers (templates/workflows-js/build-feature.js and build-ticket.js), engagements of the declared restructuring specialist are bounded by their own constant, MAX_SPECIALIST_ENGAGEMENTS = 1, separate from MAX_RETRIES. A restructure that fell short is not transient. Each accepted engagement is recorded in restructureLog. If the check refuses again on the same terms after the bound is reached, the run stops as restructuring_unmet. The stop names what the specialist was asked to do and where the file now stands (describeDemand), says the specialist's changes remain in place, and confirms that nothing was delivered and the standard was not relaxed. If the specialist itself returns blocker or failed, the run stops as restructuring_unavailable. That is reported as a failure of the machinery, so the file's standing is unknown and nothing is delivered; it does not enter blocker classification and retry. Both drivers were already over their size limit, so the change repays its lines by removing blank lines only. Tests: unit_tests/workflows/test_bo_3800d_1.py, _2.py and _3.py (shared _bo3800d_support.py). BO-3800d and its children are marked done."
breaking: false
---

## Entry
