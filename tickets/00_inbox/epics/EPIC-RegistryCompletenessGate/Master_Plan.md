---
epic_name: EPIC-RegistryCompletenessGate
created: 2026-06-22
status: in_progress
components:
  - build_pipeline
source_ac: BP-900e
---
# EPIC-RegistryCompletenessGate

## Goal

This epic implements AC BP-900e: Build catches package capabilities promised in the registry but never shipped to consumers. It consists of 7 ticket(s) generated from the leaf ACs beneath BP-900e, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260622-BP-900e-1.md](./01_TICKET-20260622-BP-900e-1.md) | A hook registered in commit_guardian.json with no template copy fails the registry-completeness gate | BP-900e-1 | BP-900e |
| 02 | [02_TICKET-20260622-BP-900e-1-i.md](./02_TICKET-20260622-BP-900e-1-i.md) | A template-referenced script with no template copy is also flagged, coordinated with the BP-900b preflight | BP-900e-1-i | BP-900e-1 |
| 03 | [03_TICKET-20260622-BP-900e-2.md](./03_TICKET-20260622-BP-900e-2.md) | A registered hook that does have a template copy passes without a false alarm | BP-900e-2 | BP-900e, BP-900e-1 |
| 04 | [04_TICKET-20260622-BP-900e-3.md](./04_TICKET-20260622-BP-900e-3.md) | A source-only script that is neither registered nor referenced is never flagged | BP-900e-3 | BP-900e, BP-900e-1 |
| 05 | [05_TICKET-20260622-BP-900e-3-i.md](./05_TICKET-20260622-BP-900e-3-i.md) | Allowlisted external scripts are exempt from the registry-completeness check | BP-900e-3-i | BP-900e-3 |
| 06 | [06_TICKET-20260622-BP-900e-4.md](./06_TICKET-20260622-BP-900e-4.md) | The failure report names each undeployed script, where it was promised, and the action to resolve it | BP-900e-4 | BP-900e, BP-900e-1 |
| 07 | [07_TICKET-20260622-BP-900e-5.md](./07_TICKET-20260622-BP-900e-5.md) | The registry-completeness check fires at the finalize merge gate, not the build preflight | BP-900e-5 | BP-900e, BP-900e-1 |

## Dependencies

```
BP-900e-1 (no dependencies)
BP-900e-1-i -> BP-900e-1
BP-900e-2 -> BP-900e-1
BP-900e-3 -> BP-900e-1
BP-900e-3-i -> BP-900e-3
BP-900e-4 -> BP-900e-1
BP-900e-5 -> BP-900e-1
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| commit | 01, 02, 03, 04, 05, 06, 07 |
| pr-reviewer | 01, 02, 03, 04, 05, 06, 07 |
| pull-request | 01, 02, 03, 04, 05, 06, 07 |
| python-coder | 01, 02, 03, 04, 05, 06, 07 |
| test-runner | 01, 02, 03, 04, 05, 06, 07 |
| test-writer | 01, 02, 03, 04, 05, 06, 07 |

