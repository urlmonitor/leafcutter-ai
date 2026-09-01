---
title: "The severity scan counted two blockers that no longer exist, and a hook registration got past the gate meant to catch it"
date: "2026-09-01"
time: "08:22"
type: manual
components: 
  - build_pipeline
summary: "Corrected two known-issue severity labels that had gone stale after fixes already shipped, downgraded a third finding now two-thirds fixed, and restructured an acceptance criterion so a hook registration that should have been refused for missing a required declaration is properly declared."
description: "2 commits (9699a62b1, 5473965fd) on build_pipeline. Downgrades KI-BP-018 from blocker to medium: two of its three findings shipped (BP-900g-9's nine fail-closed record_deploy_failure sites plus raise_if_deploy_failures; BP-900g-8's intra-package closure guard), leaving only the hand-listed deploy set (~26 places) open — real but now maintenance debt rather than a blocker, since a missing declared source now stops the build and names the phase and path instead of shipping a silently incomplete install. Also relabels KI-BP-003 and KI-BP-006, both re-verified as already RESOLVED (_find_doc_types_json's ancestor walk covering both layouts; _ac_components.py's six call sites including the AC-store deploy map) but still carrying 'Severity: blocker' headers, which had inflated a severity scan of the register by two nonexistent blockers.

Second commit declares the package surface BP-1100g-5-i actually registers: commit 406375c88 added the check-ticket-signoff-parity hook to commit_guardian.json — a watched registry path — with no package_surface field, which is exactly the combination ACS-100i-8 exists to refuse, and should have been refused when it landed. Setting package_surface: true triggers ACS-100i-6's five-field it_requirements object; the AC's nine prose constraints are preserved byte-identical under a new constraints array, the shape BP-1100g-4 already uses for the same kind of registration. Four of the nine — the anti-grep clause, the BO-1000b-1-i template-literal trap, the legacy pre-epoch carve-out, and the report-is-not-a-verdict scope bound — have no home among the five required fields at all, being test-strategy rules and scope limits rather than behavioural requirements, so they stay in constraints rather than being placed by desperation. Where a constraint had genuine machine-checkable substance it was also lifted into the schema (the three shortfall kinds became an output enum). Filed as the declaration half of KI-BP-20260901-0812; how the undeclared registration got past ACS-100i-8 when it landed is left open."
commits: 
  - 9699a62b1
  - 5473965fd
breaking: false
---

## Entry
