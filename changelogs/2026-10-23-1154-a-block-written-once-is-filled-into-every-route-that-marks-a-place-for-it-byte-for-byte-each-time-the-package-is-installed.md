---
title: "A block written once is filled into every route that marks a place for it, byte for byte, each time the package is installed"
date: "2026-10-23"
time: "11:54"
type: manual
components: 
  - build_pipeline
  - build_orchestration
summary: "The install now checks every workflow route and shared block in one pass, reports every problem with route path, line and block name, and writes nothing if any problem is found."
description: "BO-4500b-1 (-i..-v): scripts/build_shared_validation.py runs before the workflow install and collects all failures: unknown block names, empty or unused block sources, stale awaiting-adoption declarations, hand-filled, nested, overlapping or unpaired markers. Each message names the route path, the 1-based marker line and the block name, and nothing is written on failure. A {{config.*}} placeholder in a block source that cannot be resolved also fails the install, naming the source, line and placeholder. A marker pair that holds text with no shared source must be declared in templates/workflows-js/_shared/hand-kept.json (BO-3900-PATH-HELPERS is declared there). Blocks awaiting adoption are declared in _shared/awaiting-adoption.json and reported on every install. scripts/build_phases_workflows.py now passes the build config into the check. Adds unit_tests/scripts/test_bo4500b_1_validation_failures.py and test_bo4500b_1_placeholder_and_hand_kept.py."
breaking: false
---

## Entry
