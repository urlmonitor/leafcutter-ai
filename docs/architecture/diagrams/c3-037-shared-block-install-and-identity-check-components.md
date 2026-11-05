---
title: "Shared Blocks — Install-Time Fill and Identity Check — Component Diagram"
description: "L3 component diagram of the shared-block mechanism as built: the block sources under templates/workflows-js/_shared/, the route templates with empty marker pairs, the workflow build phase that validates and fills them (one step, two blocks: WORKSPACE-ANSWER and COMMIT-ANSWER), the commit step's configuration feeding that install through placeholders, the installed routes, and the identity check that reads the installed routes. COMMIT-ANSWER's consuming routes are planned and awaiting adoption; build-feature and build-ticket sit outside that set."
type: architecture
flight_level: L3-Component
diagram_type: component
status: draft
parent: docs/architecture/components/build-orchestration.md
created: 2026-10-23
last_updated: 2026-10-23
source_ticket: null
components:
  - build_orchestration
  - build_pipeline
  - documentation_system
related_docs:
  - docs/architecture/components/build-orchestration.md
  - docs/architecture/adrs/ADR-030-dual-engine-workflow-support.md
  - docs/reference/shared-blocks.md
  - docs/reference/shared-commit-step.md
related_code:
  - templates/workflows-js/_shared/workspace-answer.js
  - templates/workflows-js/_shared/commit-answer.js
  - templates/workflows-js/_shared/awaiting-adoption.json
  - templates/workflows-js/_shared/hand-kept.json
  - scripts/build_phases_workflows.py
  - scripts/build_shared_blocks.py
  - scripts/build_shared_validation.py
  - scripts/shared_block_identity.py
  - unit_tests/scripts/test_bo4500b_2_deployed_layout.py
  - config/commit_step.json
tags:
  - shared-blocks
  - workflow-build
  - commit-answer
  - workspace-answer
  - BO-4500b-5
---

# Shared Blocks — Install-Time Fill and Identity Check — Component Diagram

Workflow bodies cannot `require` a module or call another workflow (ADR-030). So logic that
several routes share is written once, as a block source. The install copies that source into an
empty marker pair in each consuming route. A test then checks that every installed copy still
matches its source byte for byte. This diagram shows the components as built on 2026-10-23.

```mermaid
C4Component
    title Shared blocks — install-time fill and identity check

    Container_Boundary(pkg, "Package source - templates/workflows-js/ and config/") {
        ComponentDb(ws_src, "_shared/workspace-answer.js", "block source WORKSPACE-ANSWER", "Acceptance of the workspace maker's answer, shellStepReply, maker dispatch helpers")
        ComponentDb(ca_src, "_shared/commit-answer.js", "block source COMMIT-ANSWER", "decideCommitAnswer(reply, history): continue / retry / engage / stop / report. Holds config.commit_step_* placeholders")
        ComponentDb(decl, "_shared/awaiting-adoption.json + hand-kept.json", "tracked declarations", "COMMIT-ANSWER awaiting adoption; BO-3900-PATH-HELPERS kept by hand")
        ComponentDb(tpl, "Route templates *.js", "top-level templates/workflows-js/*.js", "Carry EMPTY marker pairs: // NAME-START ... // NAME-END")
        ComponentDb(cfg, "config/commit_step.json", "commit step configuration", "answer_version, max_transient_retries, reason_codes families")
    }

    Container_Boundary(inst, "Install step - build.py workflow build phase") {
        Component(phase, "build_workflow_scripts", "build_phases_workflows.py", "One step for every block: validate, fill, engine variant, inject_config, compare-before-write")
        Component(val, "validate_or_fail", "build_shared_validation.py", "Checks the whole route set before any write; refuses on any problem")
        Component(fill, "inline_shared_blocks", "build_shared_blocks.py", "Fills each empty pair from _shared/NAME.js; resolves commit_step_* via load_commit_step_values")
    }

    Container_Boundary(out, "Installed routes - output_root/workflows/*.js") {
        Component(ws_routes, "WORKSPACE-ANSWER carriers", "installed routes, filled", "build-epic, build-feature, build-ticket, fast-lane-ship, finalize-feature, plan-feature, quick-fix")
        Component(ca_planned, "COMMIT-ANSWER consumers - PLANNED", "awaiting adoption, no marker pair yet", "fast-lane-ship, plan-feature, quick-fix, finalize-feature, commit.js (/commit)")
        Component(ca_outside, "Outside the COMMIT-ANSWER set", "keep BO-3000a phase-loop routing", "build-feature, build-ticket")
    }

    Container_Boundary(tests, "Test suite") {
        Component(ident, "check_identity", "shared_block_identity.py", "Reads INSTALLED *.js bytes under the layout root, every deployed location; never templates")
        Component(t_dep, "test_bo4500b_2_deployed_layout", "pytest, shared_layout_reader", "Runs the check on the shared reference layout with the real build config")
    }

    Rel(phase, val, "1. validate all routes and sources")
    Rel(tpl, val, "marker pairs scanned")
    Rel(decl, val, "awaiting / hand-kept read")
    Rel(phase, fill, "2. fill empty marker pairs")
    Rel(ws_src, fill, "block text")
    Rel(ca_src, fill, "block text")
    Rel(cfg, fill, "placeholder values, install time only")
    Rel(phase, ws_routes, "3. writes filled routes")
    Rel(phase, ca_outside, "3. writes, no COMMIT-ANSWER pair")
    Rel(ca_src, ca_planned, "planned, not yet adopted")
    Rel(t_dep, ident, "calls")
    Rel(ident, ws_routes, "reads installed bytes")
    Rel(ident, fill, "reuses the install's resolution")
    Rel(ident, decl, "awaiting / hand-kept read")

    UpdateElementStyle(ca_planned, $bgColor="#9e9e9e", $borderColor="#616161")
    UpdateElementStyle(ca_outside, $bgColor="#8d6e63", $borderColor="#5d4037")
    UpdateRelStyle(ca_src, ca_planned, $lineColor="#9e9e9e", $textColor="#616161")
```

Parent: [Build Orchestration — Epic & Ticket Dispatch Sequencing](../components/build-orchestration.md)

See also: [Shared blocks reference](../../reference/shared-blocks.md) (the marker grammar),
[Install failures](../../reference/shared-block-install-failures.md) (each
install failure's text) and [ADR-030](../adrs/ADR-030-dual-engine-workflow-support.md) (why
workflow bodies cannot share code at run time). The commit step's own component diagram
(BO-4500a-5-ix) is not drawn yet. When it is, it links here for this mechanism rather than
redrawing it.

## Legend and notes

**Colours.** Grey is planned and not built: no installed route carries COMMIT-ANSWER yet. Brown
is outside the COMMIT-ANSWER set. The grey arrow from the COMMIT-ANSWER source is a plan, not
a fill.

**One step, two blocks.** WORKSPACE-ANSWER and COMMIT-ANSWER are two blocks on the same install
step. The build has no list of blocks or of consumers. A block is a file `_shared/<name>.js`,
and its name is that file name in capitals. A consumer is any top-level route template with a
marker pair. Adding a block means adding a source and a marker pair. The install code does not
change.

**Order inside the step.** `build_workflow_scripts` first runs `validate_or_fail` over every
route template and every block source. It collects every problem (unknown, empty, unused or
stale-declared block, a hand-filled pair, nested, overlapping or unpaired markers, a placeholder
it cannot resolve). If there is any problem, nothing is filled or written. Then each template's
empty pairs are filled. Then the engine variant is emitted and `inject_config` resolves the
route's own `{{config.*}}` placeholders. Last, compare-before-write skips any file that has not
changed. Templates keep their empty pairs; only installed routes hold the filled text.

**The commit step's configuration feeds the install, not the routes.** `commit-answer.js`
holds `{{config.commit_step_*}}` placeholders. `load_commit_step_values` fills them from
`config/commit_step.json` during the install. Installed routes read no file at run time
(ADR-030). A change to `commit_step.json` reaches a route only through the next install.

**The identity check reads installed routes.** `check_identity` walks every `*.js` under the
deployed layout root, so it covers every deployed location. It never reads templates. It
renders the expected text with the install's own resolution (`_block_text`, then
`inject_config`) and compares bytes. It names each route and block that differs and its first
differing line. It fails if it inspected zero copies. It reports COMMIT-ANSWER as "not
inspected because it awaits adoption", and it reports hand-kept pairs as not checked, without
failing.

**How this differs from BP-1000e.** BP-1000e compares one workflow *file* with its shipped
mirror copy: the whole file, one source to one copy, at the merge gate. This mechanism keeps one
*block* the same across *many* installed routes. It compares only the text between a marker
pair, against the block source as the install renders it. They check different things, and
neither one replaces the other. BP-1000e is not built yet (`work_status: todo`), and this tree has
no `scripts/workflows/` mirror directory.

## Built names win; differences noted

Where the BO-4500b-5 criteria wording and the built code differ, the diagram uses the built
names:

| Criteria wording | As built |
|---|---|
| block sources | `templates/workflows-js/_shared/<name>.js` (`workspace-answer.js`, `commit-answer.js`) |
| the install step that fills them | `build_workflow_scripts` in `scripts/build_phases_workflows.py`, calling `validate_or_fail` (`scripts/build_shared_validation.py`) and `inline_shared_blocks` / `fill_template_bytes` (`scripts/build_shared_blocks.py`) |
| the /commit route | `templates/workflows-js/commit.js` |
| COMMIT-ANSWER's consuming routes | **None consumes it yet.** No route template has a `// COMMIT-ANSWER-START` pair. `_shared/awaiting-adoption.json` declares the block as awaiting adoption by BO-4500a-5-i, -ii, -iii, -iv and BO-4500b-1-ii. The five routes are drawn as planned. |
| the commit step's configuration | `config/commit_step.json`, read through `{{config.commit_step_*}}` placeholders in the block source |
| the identity check | `check_identity` in `scripts/shared_block_identity.py`, run by `unit_tests/scripts/test_bo4500b_2_deployed_layout.py` |
| build-feature and build-ticket outside the set | True for COMMIT-ANSWER. Both still carry WORKSPACE-ANSWER. |

Also built but not named in the criteria:

- `build-epic.js` carries WORKSPACE-ANSWER.
- `create-ticket.js` carries no marker pair.
- `_shared/hand-kept.json` declares the `BO-3900-PATH-HELPERS` pairs in `build-feature.js` and
  `plan-feature.js` as hand copies. The install does not fill them, and the identity check does
  not compare them. Moving them to a `_shared` source is follow-up work.
