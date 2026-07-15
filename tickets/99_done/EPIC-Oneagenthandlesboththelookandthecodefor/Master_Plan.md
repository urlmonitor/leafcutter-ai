---
epic_name: EPIC-OneAgentHandlesBothTheLookAndTheCodeFor
created: 2026-06-08
status: done
components:
  - build_pipeline
source_ac: BP-700
---
# EPIC-OneAgentHandlesBothTheLookAndTheCodeFor

## Goal

This epic implements AC BP-700: One agent handles both the look and the code for your frontend. It consists of 18 ticket(s) generated from the leaf ACs beneath BP-700, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260608-BP-700a-1-i.md](./01_TICKET-20260608-BP-700a-1-i.md) | Legacy frontend-design skill file is ignored when unified agent is deployed | BP-700a-1-i | BP-700a-1 |
| 02 | [02_TICKET-20260608-BP-700a-2.md](./02_TICKET-20260608-BP-700a-2.md) | Agent applies design principles without explicit skill activation | BP-700a-2 | BP-700a, BP-700a-1 |
| 03 | [03_TICKET-20260608-BP-700a-3.md](./03_TICKET-20260608-BP-700a-3.md) | Project design system overrides embedded principles | BP-700a-3 | BP-700a, BP-700a-1 |
| 04 | [04_TICKET-20260608-BP-700a-4.md](./04_TICKET-20260608-BP-700a-4.md) | How-to guide documents design integration for adopters | BP-700a-4 | BP-700a, BP-700a-1 |
| 05 | [05_TICKET-20260608-BP-700a-5.md](./05_TICKET-20260608-BP-700a-5.md) | Component diagram shows unified agent in the dispatch topology | BP-700a-5 | BP-700a, BP-700a-1 |
| 06 | [06_TICKET-20260608-BP-700b-1.md](./06_TICKET-20260608-BP-700b-1.md) | Agent registry entry has default_status not_needed | BP-700b-1 | BP-700b |
| 07 | [07_TICKET-20260608-BP-700b-2-i.md](./07_TICKET-20260608-BP-700b-2-i.md) | LLM trigger fires for tickets describing UI work without frontend file extensions in files_touched | BP-700b-2-i | BP-700b-2 |
| 08 | [08_TICKET-20260608-BP-700b-3.md](./08_TICKET-20260608-BP-700b-3.md) | Agent produces no output or side effects when not dispatched | BP-700b-3 | BP-700b, BP-700b-1 |
| 09 | [09_TICKET-20260608-BP-700c-1.md](./09_TICKET-20260608-BP-700c-1.md) | All frontend-design skill principles are present in unified template | BP-700c-1 | BP-700c |
| 10 | [10_TICKET-20260608-BP-700c-2.md](./10_TICKET-20260608-BP-700c-2.md) | All frontend-coder agent capabilities are preserved in unified template | BP-700c-2 | BP-700c |
| 11 | [11_TICKET-20260608-BP-700c-3.md](./11_TICKET-20260608-BP-700c-3.md) | Webapp-testing skill integration preserved as optional | BP-700c-3 | BP-700c |
| 12 | [12_TICKET-20260608-BP-700c-4.md](./12_TICKET-20260608-BP-700c-4.md) | Agent registry entry preserves all existing selection criteria and metadata | BP-700c-4 | BP-700c |
| 13 | [13_TICKET-20260608-BP-700c-5.md](./13_TICKET-20260608-BP-700c-5.md) | Reference document catalogues all preserved capabilities | BP-700c-5 | BP-700c, BP-700c-1, BP-700c-2 |
| 14 | [14_TICKET-20260608-BP-700d-1-i.md](./14_TICKET-20260608-BP-700d-1-i.md) | Fresh install without prior frontend-design skill succeeds cleanly | BP-700d-1-i | BP-700d-1 |
| 15 | [15_TICKET-20260608-BP-700d-1-ii.md](./15_TICKET-20260608-BP-700d-1-ii.md) | Upgrade with customised PROJECT_CONTEXT.md preserves project design system | BP-700d-1-ii | BP-700d-1 |
| 16 | [16_TICKET-20260608-BP-700d-2.md](./16_TICKET-20260608-BP-700d-2.md) | Onboard wizard no longer offers frontend-design as a separate optional skill | BP-700d-2 | BP-700d |
| 17 | [17_TICKET-20260608-BP-700d-3.md](./17_TICKET-20260608-BP-700d-3.md) | skills_config.json frontend key updated to remove frontend-design reference | BP-700d-3 | BP-700d, BP-700d-1 |
| 18 | [18_TICKET-20260608-BP-700d-4.md](./18_TICKET-20260608-BP-700d-4.md) | How-to guide documents upgrade path for existing adopters | BP-700d-4 | BP-700d, BP-700d-1 |

## Dependencies

```
BP-700a-1-i (no dependencies)
BP-700a-2 (no dependencies)
BP-700a-3 (no dependencies)
BP-700a-4 (no dependencies)
BP-700a-5 (no dependencies)
BP-700b-1 (no dependencies)
BP-700b-2-i -> BP-700b-1
BP-700b-3 -> BP-700b-1
BP-700c-1 (no dependencies)
BP-700c-2 (no dependencies)
BP-700c-3 (no dependencies)
BP-700c-4 (no dependencies)
BP-700c-5 -> BP-700c-1, BP-700c-2
BP-700d-1-i (no dependencies)
BP-700d-1-ii (no dependencies)
BP-700d-2 (no dependencies)
BP-700d-3 (no dependencies)
BP-700d-4 (no dependencies)
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| architecture-diagram-author | 05 |
| commit | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18 |
| documentation-expert | 04, 13, 18 |
| llm-expert | 01, 02, 03, 09, 10, 11, 16 |
| pr-reviewer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18 |
| pull-request | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18 |
| python-coder | 06, 12, 14, 15, 17 |
| test-runner | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18 |
| test-writer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18 |

