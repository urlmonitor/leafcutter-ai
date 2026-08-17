---
title: "EPIC: Deployment Completeness"
type: epic
epic_name: EPIC-DeploymentCompleteness
created: 2026-06-11
status: in_progress
components:
  - build_pipeline
source_ac: BP-900
depends_on: []
priority: critical
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
change_target: pipeline
risk_surface: contract_boundary
---
# EPIC-DeploymentCompleteness

## Goal

This epic implements AC BP-900: Every leafcutter capability you install actually works when you use it. It consists of 14 ticket(s) generated from the leaf ACs beneath BP-900, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

Tickets 01-11 were generated 2026-06-11 from the BP-900a/b/c leaf ACs. Tickets
12-14 were added 2026-08-17 from the new BP-900h branch — see "Scope addition"
below.

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
| 12 | [12_TICKET-20260817-BP-900h-1.md](./12_TICKET-20260817-BP-900h-1.md) | CI installs the package into an empty project and the build succeeds | BP-900h-1 | — |
| 13 | [13_TICKET-20260817-BP-900h-2.md](./13_TICKET-20260817-BP-900h-2.md) | Two consecutive builds into the same project produce zero difference | BP-900h-2 | 12 |
| 14 | [14_TICKET-20260817-BP-900h-3.md](./14_TICKET-20260817-BP-900h-3.md) | A broken consumer install blocks the merge, it does not just report | BP-900h-3 | 12, 13 |

## Scope addition — BP-900h (2026-08-17)

Tickets 12-14 were added after this epic was scoped, from a new L1 branch
`BP-900h` ("Know the clean install works, because every change proves it").

**Why.** BP-900a..BP-900g all verify deployment completeness *statically*, from
inside the build. None of them performs an install and inspects the result. That
left phase_1 exit criteria 1 and 3 in `docs/roadmap.json` — "clean install
succeeds on a blank project" and "consecutive builds produce zero git diff" —
with no automated check anywhere, while seven consumer-install defects
(BP-900g-4/-5/-6, BP-015, BP-016, BP-017, BP-018) shipped and were hotfixed after
release between 2026-08-13 and 2026-08-17.

**Sequencing.** All three edit `.github/workflows/ci.yml`, so they are chained
12 → 13 → 14 and must not be batched in parallel with each other. They are
independent of tickets 01-11 and may run alongside them.

**Manual handoff in ticket 14.** Registering the new job as a *required* status
check is a repository ruleset change (`require-ci-lint`, id `17810993`) needing an
`admin:write` token. It cannot be done from the workflow file, and the job must be
green on `main` before it is marked required — marking it required while red
blocks every merge in the repository.

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

