---
title: "EPIC: Web-app CI safety net (BP-1400)"
type: epic
epic_name: EPIC-ChangesToTheWebAppCantReachUsersBroken
created: 2026-07-21
status: in_progress
components:
  - build_pipeline
depends_on: []
change_target: pipeline
risk_surface: safety
requires_diagram: false
requires_adr: false
source_ac: BP-1400
---
# EPIC-ChangesToTheWebAppCantReachUsersBroken

## Goal

This epic implements AC BP-1400: Changes to the web app can't reach users broken. It consists of 11 ticket(s) generated from the leaf ACs beneath BP-1400, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260721-BP-1400a-1.md](./01_TICKET-20260721-BP-1400a-1.md) | A blocking build and type-check check runs on every web-app pull request and fails on any build or type error | BP-1400a-1 | BP-1400a |
| 02 | [02_TICKET-20260721-BP-1400a-1-i.md](./02_TICKET-20260721-BP-1400a-1-i.md) | A web-app change that introduces a TypeScript type error is blocked from merging | BP-1400a-1-i | BP-1400a-1 |
| 03 | [03_TICKET-20260721-BP-1400a-2.md](./03_TICKET-20260721-BP-1400a-2.md) | The web-app build/type-check check is required only for pull requests that change the web app | BP-1400a-2 | BP-1400a |
| 04 | [04_TICKET-20260721-BP-1400a-2-i.md](./04_TICKET-20260721-BP-1400a-2-i.md) | A pull request that changes both a web-app file and a non-web-app file still requires the web-app check to pass | BP-1400a-2-i | BP-1400a-2 |
| 05 | [05_TICKET-20260721-BP-1400a-3.md](./05_TICKET-20260721-BP-1400a-3.md) | Sequence diagram documents the web-app CI gate flow from pull request to merge decision | BP-1400a-3 | BP-1400a, BP-1400a-1 |
| 06 | [06_TICKET-20260721-BP-1400b-1.md](./06_TICKET-20260721-BP-1400b-1.md) | A blocking style check runs on every web-app pull request and fails on any style-rule violation | BP-1400b-1 | BP-1400b |
| 07 | [07_TICKET-20260721-BP-1400b-1-i.md](./07_TICKET-20260721-BP-1400b-1-i.md) | A web-app file containing an unescaped-entity style error blocks the pull request from merging | BP-1400b-1-i | BP-1400b-1 |
| 08 | [08_TICKET-20260721-BP-1400c-1.md](./08_TICKET-20260721-BP-1400c-1.md) | A blocking route-render check headlessly loads every web-app route and fails on a non-200 or a console/render error | BP-1400c-1 | BP-1400c |
| 09 | [09_TICKET-20260721-BP-1400a-4.md](./09_TICKET-20260721-BP-1400a-4.md) | Every web-app check reports its result on the pull request and gates the merge | BP-1400a-4 | BP-1400a, BP-1400a-1, BP-1400b-1, BP-1400c-1 |
| 10 | [10_TICKET-20260721-BP-1400c-1-i.md](./10_TICKET-20260721-BP-1400c-1-i.md) | The /about route is loaded headlessly and a non-200 or render error on it blocks the pull request | BP-1400c-1-i | BP-1400c-1 |
| 11 | [11_TICKET-20260721-BP-1400c-2.md](./11_TICKET-20260721-BP-1400c-2.md) | Sequence diagram documents the web-app route-render check flow | BP-1400c-2 | BP-1400c, BP-1400c-1 |

## Dependencies

```
BP-1400a-1 (no dependencies)
BP-1400a-1-i -> BP-1400a-1
BP-1400a-2 (no dependencies)
BP-1400a-2-i -> BP-1400a-2
BP-1400a-3 -> BP-1400a-1
BP-1400a-4 -> BP-1400a-1, BP-1400b-1, BP-1400c-1
BP-1400b-1 (no dependencies)
BP-1400b-1-i -> BP-1400b-1
BP-1400c-1 (no dependencies)
BP-1400c-1-i -> BP-1400c-1
BP-1400c-2 -> BP-1400c-1
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| ac-fulfillment-gate | 01, 02, 03, 04, 06, 07, 08, 09, 10 |
| ac-validator | 01, 02, 03, 04, 06, 07, 08, 09, 10 |
| architect-review | 01, 02, 03, 04, 06, 07, 08, 09, 10 |
| architecture-diagram-author | 05, 11 |
| commit | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11 |
| documentation-expert | 05, 11 |
| pr-reviewer | 01, 02, 03, 04, 06, 07, 08, 09, 10 |
| pull-request | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11 |
| python-coder | 01, 02, 03, 04, 06, 07, 08, 09, 10 |
| test-runner | 01, 02, 03, 04, 06, 07, 08, 09, 10 |
| test-writer | 01, 02, 03, 04, 06, 07, 08, 09, 10 |

