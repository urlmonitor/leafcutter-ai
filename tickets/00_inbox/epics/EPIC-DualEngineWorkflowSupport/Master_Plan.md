---
title: "EPIC: Dual-Engine Workflow Support — port scripts to the live contract"
type: epic
status: in_progress
components:
  - build_pipeline
  - supervisor_system
created: 2026-07-01
depends_on: []
requires_diagram: false
requires_adr: true
---

# EPIC: Dual-Engine Workflow Support

## Goal

Make leafcutter's workflow scripts (`plan-feature`, `finalize-feature`,
`build-epic`, `build-ticket`, `quick-fix`) actually **execute** in the live
Claude Code environment, deterministically, while preserving forward-compat
for the alternate engine contract — and make silent no-op regressions
impossible to ship.

## Context / Root Cause (proven 2026-07-01)

There are two incompatible Claude Code workflow-engine contracts:

- **E2 (the engine that actually runs here):** executes the script's
  **top-level body**; primitives are globals `agent(prompt, {agentType, schema})`,
  `parallel()`, `pipeline()`, `phase()`, `log()`, `args`, `workflow()`, `budget`.
- **E1 (the contract most repo scripts were written for):**
  `export async function run({agent, workflow, parallel, userInput})` with NO
  top-level call, and `agent({agentType, input})`.

Two zero-side-effect probes confirmed the live engine executes top-level bodies
and **never invokes an exported `run()`** — even by named-workflow resolution, on
Claude Code 2.1.185. So `plan-feature.js`, `finalize-feature.js`, `build-epic.js`,
`build-ticket.js` are **silent no-ops** today; `/build-feature` only "works" via
an inline LLM prose fallback (a determinism liability). `quick-fix.js` is already
authored in E2 form and **works** — it is the reference pattern for the port.

Official Claude Code docs cover *running* Claude-generated workflows but do **not**
document a hand-authoring contract; the only concrete API reference in the
changelog (`Workflow tool agent({schema})`, v2.1.174/186) matches E2, not E1. The
`run()`-export contract appears never to have been officially supported. (Escalation
to the internal Claude Code team is tracked outside this epic.)

## Strategy

Author workflows **once in E2 canonical form** (what provably runs), and emit an
E1-wrapped variant at build time so both engines are covered. No LLM fallbacks —
if the engine is absent, fail loudly. Add a CI guard that fails when any workflow
dispatches zero agents, converting the silent-no-op failure class into a loud one.

## Tickets

| # | File | Description | Depends On | Status |
|---|------|-------------|------------|--------|
| 01 | [01_config_workflow_engine_keys.md](./01_config_workflow_engine_keys.md) | Add `workflows.enabled` + `workflows.engine` to config schema + defaults | — | `[ ]` |
| 02 | [02_ci_zero_dispatch_guard.md](./02_ci_zero_dispatch_guard.md) | Dual-engine test harness + zero-agent-dispatch CI guard (stop-the-bleed) | — | `[ ]` |
| 03 | [03_canonical_e2_contract_and_adr.md](./03_canonical_e2_contract_and_adr.md) | Spike E2 edges; ADR + canonical E2 authoring template & E1-wrap shim spec | — | `[ ]` |
| 04 | [04_build_time_variant_transform.md](./04_build_time_variant_transform.md) | `_emit_workflow_variant` transform in build_phases.py (identity E2 / wrap E1) | 01, 03 | `[ ]` |
| 05 | [05_port_build_epic_and_build_ticket.md](./05_port_build_epic_and_build_ticket.md) | Port `build-epic.js` + `build-ticket.js` to E2 canonical | 03, 04 | `[ ]` |
| 06 | [06_port_plan_feature_and_finalize_feature.md](./06_port_plan_feature_and_finalize_feature.md) | Port `plan-feature.js` + `finalize-feature.js` to E2 canonical | 03, 04 | `[ ]` |
| 07 | [07_default_flip_and_command_wiring.md](./07_default_flip_and_command_wiring.md) | Default engine → E2, version-as-floor, wire command bodies to Workflow tool (no LLM fallback) | 05, 06 | `[ ]` |

## Dependencies

```
01 (no deps)
02 (no deps)
03 (no deps)
04 -> 01, 03
05 -> 03, 04
06 -> 03, 04
07 -> 05, 06
```

## Out of Scope

- AC↔ticket de-duplication guard (`generate_ticket_from_ac.py` `implemented_by`
  gate + integrity-hook `source_ac` check) — related but a separate concern;
  tracked as its own ticket.
- Escalation to the internal Claude Code team for official workflow-authoring docs.
