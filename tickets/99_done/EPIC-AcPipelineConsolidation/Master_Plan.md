---
epic_name: EPIC-AcPipelineConsolidation
created: 2026-06-10
status: done
components:
  - ac-driven-dev
source_ac: ACD-1100
---
# EPIC-AcPipelineConsolidation

## Goal

This epic implements AC ACD-1100: The AC-driven development pipeline is the only pipeline — no legacy alternatives remain. It consists of 14 ticket(s) generated from the leaf ACs beneath ACD-1100, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260610-ACD-1100a-1.md](./01_TICKET-20260610-ACD-1100a-1.md) | Legacy pipeline agent templates are deleted from the package | ACD-1100a-1 | ACD-1100a |
| 02 | [02_TICKET-20260610-ACD-1100a-2.md](./02_TICKET-20260610-ACD-1100a-2.md) | Legacy pipeline agent registry entries are removed | ACD-1100a-2 | ACD-1100a |
| 03 | [03_TICKET-20260610-ACD-1100a-3.md](./03_TICKET-20260610-ACD-1100a-3.md) | No workflow or skill dispatches a removed legacy agent | ACD-1100a-3 | ACD-1100a, ACD-1100a-2 |
| 04 | [04_TICKET-20260610-ACD-1100b-1.md](./04_TICKET-20260610-ACD-1100b-1.md) | V3 agent template files are renamed to canonical names | ACD-1100b-1 | ACD-1100b, ACD-1100a |
| 05 | [05_TICKET-20260610-ACD-1100b-2.md](./05_TICKET-20260610-ACD-1100b-2.md) | Agent registry entries use canonical names without version suffixes | ACD-1100b-2 | ACD-1100b, ACD-1100a-2 |
| 06 | [06_TICKET-20260610-ACD-1100b-3.md](./06_TICKET-20260610-ACD-1100b-3.md) | All cross-references to v3 agent names are updated to canonical names | ACD-1100b-3 | ACD-1100b, ACD-1100b-1, ACD-1100b-2 |
| 07 | [07_TICKET-20260610-ACD-1100b-3-i.md](./07_TICKET-20260610-ACD-1100b-3-i.md) | Edge case: no agent in the entire registry carries any version suffix | ACD-1100b-3-i | ACD-1100b-3 |
| 08 | [08_TICKET-20260610-ACD-1100c-1.md](./08_TICKET-20260610-ACD-1100c-1.md) | Skill directory and registry entry use the name plan-feature | ACD-1100c-1 | ACD-1100c |
| 09 | [09_TICKET-20260610-ACD-1100c-2.md](./09_TICKET-20260610-ACD-1100c-2.md) | Old /create-ac command surface is fully absent | ACD-1100c-2 | ACD-1100c, ACD-1100c-1 |
| 10 | [10_TICKET-20260610-ACD-1100d-1.md](./10_TICKET-20260610-ACD-1100d-1.md) | product-owner-agent and test-planner are fully removed | ACD-1100d-1 | ACD-1100d |
| 11 | [11_TICKET-20260610-ACD-1100e-1.md](./11_TICKET-20260610-ACD-1100e-1.md) | Version file exists with semver 2.0.0 | ACD-1100e-1 | ACD-1100e |
| 12 | [12_TICKET-20260610-ACD-1100e-2.md](./12_TICKET-20260610-ACD-1100e-2.md) | Build output references the package version | ACD-1100e-2 | ACD-1100e, ACD-1100e-1 |
| 13 | [13_TICKET-20260610-ACD-1100f-1.md](./13_TICKET-20260610-ACD-1100f-1.md) | Historical origin_agent values pass AC schema validation | ACD-1100f-1 | ACD-1100f |
| 14 | [14_TICKET-20260610-ACD-1100f-1-i.md](./14_TICKET-20260610-ACD-1100f-1-i.md) | Edge case: origin_agent accepts any historical agent name without allowlist | ACD-1100f-1-i | ACD-1100f-1 |

## Dependencies

```
ACD-1100a-1 (no dependencies)
ACD-1100a-2 (no dependencies)
ACD-1100a-3 -> ACD-1100a-2
ACD-1100b-1 (no dependencies)
ACD-1100b-2 -> ACD-1100a-2
ACD-1100b-3 -> ACD-1100b-1, ACD-1100b-2
ACD-1100b-3-i -> ACD-1100b-3
ACD-1100c-1 (no dependencies)
ACD-1100c-2 -> ACD-1100c-1
ACD-1100d-1 (no dependencies)
ACD-1100e-1 (no dependencies)
ACD-1100e-2 -> ACD-1100e-1
ACD-1100f-1 (no dependencies)
ACD-1100f-1-i -> ACD-1100f-1
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| commit | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14 |
| llm-expert | 01, 04, 08, 10 |
| pr-reviewer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14 |
| pull-request | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14 |
| python-coder | 02, 03, 05, 06, 07, 09, 11, 12, 13, 14 |
| test-runner | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14 |
| test-writer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14 |

