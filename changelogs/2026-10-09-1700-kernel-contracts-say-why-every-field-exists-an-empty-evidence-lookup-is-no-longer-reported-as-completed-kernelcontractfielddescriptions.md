---
title: "Kernel contracts say why every field exists; an empty evidence lookup is no longer reported as completed (#KernelContractFieldDescriptions)"
date: "2026-10-09"
time: "17:00"
type: manual
components: 
  - decision_kernel
summary: "Every field of the kernel's contracts now carries a short purpose that is emitted into the JSON schemas hosts and LLMs receive (588 of 588 properties). An evidence lookup for which no evidence need was selected now plans baseline needs instead of searching nothing, and a bundle with no planned need is reported as partial with the limitation that no research ran."
description: "Tickets KernelContractFieldDescriptions and KernelEvidenceLookupNoNeeds. Field purposes are Pydantic attribute docstrings (use_attribute_docstrings), guarded by tests/kernel/contracts/test_schema_descriptions.py. The trusted knowledge copy of the decision schema was re-pinned (descriptions only). The lookup regression was seen in kernel run run-124d6a01a27c442c."
---

## Entry
