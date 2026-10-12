---
title: "A proof that never went through a real way in does not make code done"
date: "2026-09-27"
time: "23:30"
type: manual
components:
  - build_orchestration
  - ac_store
summary: "Done-proof eligibility gains two reachability checks: a criterion whose passing tests only import the code directly is refused when the code has a real entry point, and code that no way of running the product reaches at all (no entry point, not imported elsewhere, not run by any automation script) is refused with two named clearing actions."
description: "EPIC-AProofThatReachedTheCodeByDirectImport: BO-2900a-1 (refusal_cause proof_bypassed_entry_point, in _done_proof_entry_point_gate.py) and BO-2900a-3 (refusal_cause no_entry_point_reaches_code, in _done_proof_automation_gate.py). The automation condition reuses the collected_invocations() seam from BO-2900b and matches invocation surfaces against the unit by resolved, case-normalised path. The refusal carries clearing_actions [give the unit an entry point, record an exemption]. The pytest subprocess used by verify_done_eligible now runs from the linked test files' common ancestor. Docs: done-proof-enforcement how-to split into a reachability-gates child; c3 done-proof sequence split likewise."
commits:
breaking: false
---

## Entry

Passing tests are no longer enough to mark a criterion done when they never touched the code the
way the product does. If the code has a real entry point but the tests only import it directly,
the criterion is refused. If no way of running the product reaches the code at all (no entry
point, nothing else imports it, and no automation script runs it), the criterion is refused too.
The message names the two ways forward: give the code an entry point, or record an exemption.
