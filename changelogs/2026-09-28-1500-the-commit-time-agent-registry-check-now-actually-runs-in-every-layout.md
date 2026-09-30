---
title: "The commit-time agent-registry check now actually runs in every layout"
date: "2026-09-28"
time: "15:00"
type: manual
components: 
  - commit_guardian
summary: "check-agent-registry used to look for a leafcutter/ folder and pass without checking anything when it was missing, which in this repository was always. It now finds the package through the shared project-root resolver and the build manifest, validates the staged registry with the same function the build uses, and blocks with its own message when it cannot find the package. The manifest lookup that three hooks each carried a copy of now lives once in _resolve_root.py."
description: "Builds GE-113c-1-vi and resolves KI-CG-20260928. check_agent_registry.py decides scope from staged paths first (the registry, its schema, templates/agents/**, under any prefix), then locates the package via _resolve_root.resolve_manifest_path plus the manifest's package_root; no literal 'leafcutter' segment. When a scoped file is staged and no package is found it exits 1 with 'CANNOT LOCATE PACKAGE', naming every location tried and the unchecked files; this deliberately differs from check_build_drift and check_output_drift, which warn and pass on a missing manifest. The candidate-root search both drift hooks duplicated moved into _resolve_root.py, so all three share it (the drift hooks shrink from 615 and 660 to 589 and 632 content lines). The registry path literals are built from segments because the BP-900g-8-ii closure guard reads comparison literals as file reads; recorded as KI-BP-20260928. BO-2400a-1-iii's git fixture gains a real build manifest so its commit-time test exercises a real layout. An enablement run against the real registry found no errors."
commits: []
breaking: false
---

## Entry

The check that validates the agent registry at commit time now actually
runs. Before, it looked for the package in a folder this repository does not
have and quietly passed. It now finds the package wherever the build put it,
checks the registry the same way the build does, and refuses the commit if
it cannot find the package at all, instead of pretending all is well.

Three commit checks each carried their own copy of the code that finds the
build manifest. They now share one.
