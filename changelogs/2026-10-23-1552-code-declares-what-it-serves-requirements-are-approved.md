---
title: "'Code declares what it serves' requirements are approved"
date: "2026-10-23"
time: "15:52"
type: manual
components: 
  - commit_guardian
  - ac_store
summary: "GE-117, the requirement that code names the requirement and component it serves, is approved and ready to plan, with test contracts on every code criterion."
description: "All 29 GE-117 records go from readiness draft to approved. The 16 code records gain test contracts (test_spec and test_rationale) and technical detail from IT-PO enrichment, and 7 how-to and diagram records are reclassified as non-code. GE-117b-1 and GE-117c-1 now depend on GE-124c-2-i, the shared AC-id resolver. GE-117e-1 infers a module's component from components.json primary_code. Its guided autofix takes the AC from the ticket the workspace maker recorded for the branch and that ticket's source_ac, never from the commit message or branch name."
breaking: false
---

## Entry
