---
title: "Product truth and the ACD-300 requirements describe the requirement pipeline as it now runs"
date: "2026-10-23"
time: "12:00"
type: manual
components:
  - ac_driven_dev
  - ux_prototyping
summary: "The ac-lifecycle flow now shows every part of the /plan-feature pipeline, and the new requirements of both epics link from the steps that implement them. Covered: the rule check after every stage, auto-gated technical planning, the code-aware test design, the hand-back rounds and the final gate that approves through approve_acs.py. The outdated ACD-300 requirement texts are amended to match."
description: "Flow ac-lifecycle v3: author, ruleCheck, stageGate, testDesign, handback and finalGate replace the old author and approve steps, each with io_contracts and an acceptance scenario. The scan and generate steps show the 'test design pending' hold. how-acs-are-built v3 links ACD-2500c-2-i and ACD-2500e-3. The generator wrote the product_truth back-links on 66 requirement records, and the validator reports checked-and-sound. In the AC store, 28 ACD-300 records were amended (business analyst) from /create-ac and 'IT PO v3' with a gate after every stage to /plan-feature, its real stages and gates and the final approval step. ACD-300d-1 now also covers the test designer. 8 records had stale contract names renamed (planner): plan-feature, ac-triage, the current template filenames and the skills frontmatter field."
breaking: false
---

## Entry
