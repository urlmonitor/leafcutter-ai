---
title: "Shared blocks are documented with a reference page, a how-to and a component diagram"
date: "2026-10-23"
time: "17:30"
type: manual
components: 
  - documentation_system
  - build_orchestration
summary: "Route authors get a reference page for shared blocks and the COMMIT-ANSWER contract, a how-to for adding a block or a consumer, and a component diagram of the install step and the identity check."
description: "Documentation for BO-4500b-4, BO-4500b-4-i and BO-4500b-5 (branch feature/bo-4500b-docs). Files changed: docs/reference/shared-blocks.md, docs/reference/shared-block-install-failures.md, docs/reference/workflow-authoring-contract.md, docs/how-to/add-a-shared-workflow-block.md, docs/architecture/diagrams/c3-037-shared-block-install-and-identity-check-components.md, docs/architecture/components/build-orchestration.md, unit_tests/reference/test_bo4500b_4_shared_blocks_reference.py, and the BO-4500b, BO-4500b-4, BO-4500b-4-i and BO-4500b-5 AC records."
breaking: false
---

## Entry

The shared-block mechanism (BO-4500b-1..3) now has the documentation its parent requirement asks for.

- `docs/reference/shared-blocks.md` states the marker convention. Its companion page
  `docs/reference/shared-block-install-failures.md` lists every install failure with the message the
  built install prints and its fix, each under a stable anchor. The main page describes
  what the identity check inspects, and the COMMIT-ANSWER contract: the reply keys, the five
  decisions, and that a specialist is engaged at most once per commit. It lists the reason-code
  families and the retry ceiling from `config/commit_step.json`. It also states that no route takes
  COMMIT-ANSWER yet, because the block still awaits adoption.
- A test reads the configuration and the page and fails when a configured reason code or the retry
  ceiling is missing from the page or differs, so the page cannot drift from the configuration.
- `docs/how-to/add-a-shared-workflow-block.md` walks through adding a new block and making a route
  consume COMMIT-ANSWER. It teaches that the whole awaiting-adoption entry is removed in the change
  that lands the first adopting route. Both procedures were walked on a scratch copy of the package.
- Diagram c3-037 shows the block sources, the route templates, the install step, the commit step's
  configuration feeding the install, the installed routes and the identity check. It also states
  how this differs from comparing a workflow file with its shipped mirror (BP-1000e).
