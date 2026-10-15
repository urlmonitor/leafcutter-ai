---
title: "Reference: Technical Planner Role"
description: "Lookup reference for what the technical planner (it-po) still does after the split, which agent or check now owns each duty it gave up, and why its lack of source access is no longer a gap."
type: reference
status: active
created: 2026-10-15
last_updated: 2026-10-15
components:
  - ac_driven_dev
  - agent_registry
related_docs:
  - templates/agents/it-po.md
  - templates/agents/test-designer.md
  - docs/reference/requirement-rule-check.md
  - docs/reference/code-aware-step.md
  - docs/reference/test-intent.md
  - docs/architecture/adrs/ADR-009-itpo-no-source-code-access.md
  - docs/architecture/adrs/ADR-071-test-intent-is-not-a-test-contract.md
  - docs/architecture/adrs/ADR-072-code-aware-test-designer-may-read-source.md
---

# Technical Planner Role

Lookup for the duties the technical planner (registered id `it-po`, template `templates/agents/it-po.md`) keeps, and the owner of each duty it gave up.

## Duties the planner keeps

| Duty | Prompt section | Note |
|---|---|---|
| Routing and splitting | S3 | One agent per AC; splits when technical boundaries show multi-agent work. |
| Sizing | 2.2 | Writes `estimated_complexity`. |
| `it_requirements` | 2.3 | Includes the package-surface object with four planner-owned keys. |
| Contracts | 2.4, 2.5, S5 | `delivers_to` and `expects_from` must agree in meaning. Presence is checked by the rule check. |
| Test intent | 2.7 | Writes `test_intent` and `test_required`. Records test intent, never test design. |
| Knowledge loop | S1, S9 | Reads injected knowledge, emits what it learned. |
| Handed-back findings | S3b | Records `decision: {choice, reason, by: it-po}` on each file finding that needs one. |
| The marker | 2.3 | Sets `hold_reason: reference file pending` only while `reference_file_path` is absent. No other `hold_reason` value, ever (ADR-072 section 6). |

The planner never writes `test_spec` and never raises `readiness` above `reviewed`.

## Relocated duty to owner

Owner `requirement rule check` is [requirement-rule-check.md](requirement-rule-check.md), run by `requirement_rule_check.py --stage itpo`.

| Relocated duty | Owner |
|---|---|
| Parent-to-child back-links | Rule check family 1 |
| Graph component list | Rule check family 2 |
| Contract presence and symmetry | Rule check family 3 |
| Restoring `readiness` if an authoring agent raised it to approved | Rule check family 4 |
| Documentation trigger to documentation requirement mapping | Rule check family 5 |
| Specialist versus surface | Rule check family 6 |
| Declared files versus `modifies` links | Rule check family 7 |
| Intent coverage of outcome clauses | Rule check family 8, `test intent coverage` |
| Test design (`test_spec`) | `test-designer`, code-aware output group |
| Reference-file choice (`reference_file_path`) | `test-designer`, file-aware output group |
| File findings (`file_findings`) | `test-designer`, file-aware output group |

The "code-aware test-design step" and the "file-aware step" are two output groups of one registered agent, `test-designer` (ADR-072 section 2). Both write onto the record in separate fields. See [code-aware-step.md](code-aware-step.md) for the pre-pass that feeds it.

## Source access

The planner does not read source code or test files (ADR-009). This is no longer a gap: the `test-designer` reads the files it needs, hands its findings back on the record, and the planner decides them (prompt section S3b). Routing and splitting stay with the planner.

## See Also

- Understand: [ADR-072](../architecture/adrs/ADR-072-code-aware-test-designer-may-read-source.md), the decision that one agent reads source.
- Decide: [ADR-071](../architecture/adrs/ADR-071-test-intent-is-not-a-test-contract.md) and [ADR-009](../architecture/adrs/ADR-009-itpo-no-source-code-access.md).
- Look up: [test-intent.md](test-intent.md) for the `test_intent` shape.
