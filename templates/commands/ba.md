---
description: |
  Invoke the Business Analyst agent for L2/L3 AC decomposition. Takes
  existing L1 ACs and decomposes them into testable Gherkin behaviors (L2)
  and edge-case specifications (L3). Produces AC YAML files as output.
  Use after /po has produced L0/L1 ACs, or to decompose an existing L1.
---

Invoke the `business-analyst` agent with the following context:

**User request:** $ARGUMENTS

**Instructions for the BA agent:**

1. Read the L0/L1 ACs the user references (or scan `docs/acceptance-criteria/` to find them).
2. For each L1, decompose into testable L2 Gherkin behaviors (Given/When/Then).
3. For each L2, identify non-obvious edge cases and failure modes as L3 ACs.
4. Check existing L2/L3 ACs under the same parent — do not duplicate what already exists.
5. Write AC YAML files to the appropriate component directory under `docs/acceptance-criteria/`.
6. Set `origin_agent: business-analyst` on all ACs you create.
7. Assign `assigned_agent`, `estimated_complexity`, and `depends_on` fields on L2/L3 ACs.
8. Log assumptions — if you inferred something not stated explicitly, call it out.
9. Present the hierarchy to the user for review before writing files.
