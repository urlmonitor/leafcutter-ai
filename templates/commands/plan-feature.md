---
description: |
  Triage, orchestrate, and gate AC authoring for a new feature request.
  Dispatches ac-triage (Haiku) to classify the request as strategic /
  behavioral / technical / covered, then routes through the correct
  authoring agents (PO v3, BA v3, IT PO v3) with user confirmation gates
  between stages. All output goes exclusively to the AC store — no ticket
  files are produced. Use when you want to plan a new feature end-to-end,
  from strategic goal down to implementable technical constraints.
---

Invoke the `plan-feature` workflow with the following context:

**User request:** $ARGUMENTS

This command runs the `/plan-feature` pipeline defined in
`scripts/workflows/plan-feature.js`. It will:

1. **Triage** the request via the `ac-triage` agent (Haiku-tier) to detect
   duplicates and classify the routing path (strategic / behavioral /
   technical / covered).
2. **Route** through the appropriate authoring agents in sequence:
   - `strategic` → PO v3 → gate → BA v3 → gate → IT PO v3 → final gate
   - `behavioral` → BA v3 → gate → IT PO v3 → final gate
   - `technical` → IT PO v3 → final gate
   - `covered` → show existing ACs → prompt cancel / amend / force
3. **Gate** at each stage — you will be shown the ACs produced and asked to
   approve, request edits, or cancel.
4. **Finalize** at the final gate: set priority and approve to mark ACs as
   `readiness: approved`.

All AC YAML files are written exclusively to `docs/acceptance-criteria/`.
No ticket files are created by this command.
