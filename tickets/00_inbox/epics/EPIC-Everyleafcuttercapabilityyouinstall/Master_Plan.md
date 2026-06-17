---
epic_name: EPIC-EveryLeafcutterCapabilityYouInstall
created: 2026-06-11
status: in_progress
components:
  - build_pipeline
source_ac: BP-900
---
# EPIC-EveryLeafcutterCapabilityYouInstall

## Goal

This epic implements AC BP-900: Every leafcutter capability you install actually works when you use it. It consists of 11 ticket(s) generated from the leaf ACs beneath BP-900, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260611-BP-900a-1.md](./01_TICKET-20260611-BP-900a-1.md) | build.py deploys all ac_store scripts to the consumer project | BP-900a-1 | BP-900a |
| 02 | [02_TICKET-20260611-BP-900a-1-1.md](./02_TICKET-20260611-BP-900a-1-1.md) | Build fails if a source ac_store script is missing from the templates directory | BP-900a-1-1 | BP-900a-1 |
| 03 | [03_TICKET-20260611-BP-900a-2.md](./03_TICKET-20260611-BP-900a-2.md) | build.py deploys standalone scripts goal_to_epic.py and build_ac_mode_detection.py | BP-900a-2 | BP-900a |
| 04 | [04_TICKET-20260611-BP-900a-3.md](./04_TICKET-20260611-BP-900a-3.md) | Deployed ac_store scripts are importable via the paths agent templates use | BP-900a-3 | BP-900a, BP-900a-1 |
| 05 | [05_TICKET-20260611-BP-900b-1.md](./05_TICKET-20260611-BP-900b-1.md) | Guard extracts script path references from all compiled agent templates and skill files | BP-900b-1 | BP-900b |
| 06 | [06_TICKET-20260611-BP-900b-1-1.md](./06_TICKET-20260611-BP-900b-1-1.md) | Allowlisted external scripts do not trigger broken-reference failures | BP-900b-1-1 | BP-900b-1 |
| 07 | [07_TICKET-20260611-BP-900b-2.md](./07_TICKET-20260611-BP-900b-2.md) | Guard cross-checks extracted references against the deployable script manifest | BP-900b-2 | BP-900b, BP-900b-1 |
| 08 | [08_TICKET-20260611-BP-900b-3.md](./08_TICKET-20260611-BP-900b-3.md) | Build exits non-zero when broken references are found | BP-900b-3 | BP-900b, BP-900b-2 |
| 09 | [09_TICKET-20260611-BP-900c-1.md](./09_TICKET-20260611-BP-900c-1.md) | Each broken-reference entry names the missing script, the referencing template, and a suggested action | BP-900c-1 | BP-900c |
| 10 | [10_TICKET-20260611-BP-900c-1-1.md](./10_TICKET-20260611-BP-900c-1-1.md) | Multiple templates referencing the same missing script produce a consolidated entry | BP-900c-1-1 | BP-900c-1 |
| 11 | [11_TICKET-20260611-BP-900c-2.md](./11_TICKET-20260611-BP-900c-2.md) | Error report is emitted to stderr in a structured, parseable format with non-zero exit | BP-900c-2 | BP-900c, BP-900c-1 |

## Dependencies

```
BP-900a-1 (no dependencies)
BP-900a-1-1 -> BP-900a-1
BP-900a-2 (no dependencies)
BP-900a-3 -> BP-900a-1
BP-900b-1 (no dependencies)
BP-900b-1-1 -> BP-900b-1
BP-900b-2 -> BP-900b-1
BP-900b-3 -> BP-900b-2
BP-900c-1 (no dependencies)
BP-900c-1-1 -> BP-900c-1
BP-900c-2 -> BP-900c-1
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| commit | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11 |
| pr-reviewer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11 |
| pull-request | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11 |
| python-coder | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11 |
| test-runner | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11 |
| test-writer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11 |

