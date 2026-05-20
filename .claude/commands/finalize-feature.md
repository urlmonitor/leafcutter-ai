---
description: >
  Supervisor agent that orchestrates the 6-step post-merge feature finalization
  sequence by dispatching existing specialists. Confirmation-gated on all destructive
  steps. Use when: user types /finalize-feature; asks to "finish this feature",
  "merge and close", or "finalize the branch".
---

Invoke the `finalize-feature` agent with the user's full request: $ARGUMENTS
