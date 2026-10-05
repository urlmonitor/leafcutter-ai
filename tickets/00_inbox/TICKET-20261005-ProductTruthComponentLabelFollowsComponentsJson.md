---
title: "Product truth: the component label check accepts docs/components.json ids"
status: todo
components:
  - ux_prototyping
created: 2026-10-05
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - product-truth
  - naming
last_updated: 2026-10-05
agents:
  test-writer: needed
  python-coder: needed
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
requires_documentation:
  - reference
---

# Product truth: the component label check accepts docs/components.json ids

## Actor / Goal
In order that the decision kernel is named the same way everywhere, we need the product-truth
label check to accept the component ids in `docs/components.json` (for example `decision_kernel`).
Then the decision flows, which already use that id, pass without a "was meant" warning.

## Context
- **User decision (2026-10-05):** the decision kernel's name follows `docs/components.json`, whose
  id is `decision_kernel`. The product-truth data keeps `decision_kernel`, and the check is what
  changes.
- **The warning today:** `validate_product_truth.py` reports one warning for each of the
  decision-kernel flows (decision-forming, decision-lifecycle, decision-publishing,
  decision-retrieval, decision-staging, and criteria-library once PR #1010 merges):
  `[label] leafcutter/decision-forming: component 'decision_kernel' is not a registered component; 'decision-kernel' was meant`.
- **Cause:** `load_component_registry` (`docs/product-truth/scripts/product_truth_label_checks.py`)
  reads the registered ids only from `docs/acceptance-criteria/index.yaml`. That file is the
  AC-store namespace/prefix registry, and its ids are hyphenated (`decision-kernel`, prefix DK).
  `docs/components.json` is not consulted.
- **Two documented axes:** the `index.yaml` header separates the scalar AC `component` field
  (namespace, hyphenated) from `components` lists (graph membership, `docs/components.json`,
  underscore ids). Every `components:` list in ACs, tickets and docs already uses `decision_kernel`.
  The hyphenated `decision-kernel` remains correct as the AC namespace and in free-form tags.
- **Docs to update:** `docs/how-to/product-truth-schema-reference.md` describes the product-truth
  `component` field as "Owning component (e.g. `ux-prototyping`)" and, for mockups, says it
  "matches an `index.yaml` key". These must name `docs/components.json` as the authority.

## Scope (no acceptance criteria yet)
- The label check resolves a flow, mock-data or mockup `component` against the ids in
  `docs/components.json`.
- Tests:
  - `decision_kernel` resolves with no warning;
  - an unknown id still warns;
  - a missing `docs/components.json` reports the check as not executed, as the missing
    `index.yaml` case does today.
- Update the schema reference wording for the `component` field of flows, mock data and mockups.

## Open Questions
- The other 21 flows use hyphenated forms (`ux-prototyping`, `knowledge-management`,
  `build-pipeline`, `ac-driven-dev`). They match `index.yaml` ids, and match `components.json` ids
  only up to the separator. Which should happen?
  - (a) The check accepts both registries for now, and the hyphenated forms keep resolving.
  - (b) The check accepts only `components.json` ids, and those flows are migrated to the
    underscore ids, with the "was meant" hint pointing at the `components.json` id.

  This is the user's call; (a) is the smaller change.

## Out of Scope
- The AC-store namespace in `docs/acceptance-criteria/index.yaml` (`decision-kernel`, prefix DK),
  the scalar `component` field of AC files, and the AC folder names. These stay hyphenated by the
  documented convention.
- Free-form `tags` values.

## Comments

## Implementation Tasks
### test-writer
- [ ] Label-check tests: a components.json id resolves, an unknown id warns, a missing registry is reported as not executed.
### python-coder
- [ ] `product_truth_label_checks.py` reads `docs/components.json` ids (plus `index.yaml` ids if open question (a) is chosen).
### documentation-expert
- [ ] Schema reference: the `component` field names `docs/components.json` as its authority.

## Risk & Safety
- Touches money? No.
- Touches data? No. A validator warning rule and its docs only.
- Reversibility? Fully reversible.
