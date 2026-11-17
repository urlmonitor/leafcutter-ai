---
title: "The closure guard walks each file once and builds each scope's names once"
date: "2026-10-25"
time: "14:45"
type: manual
components: 
  - build_pipeline
summary: "The build's deploy-completeness closure guard now walks each file's syntax tree once and builds each scope's names once, instead of seven walks per file and one name map per path expression. Its CPU time roughly halves and its verdicts are unchanged."
description: "perf(build), BP-900g-8-iv (parent BP-900g-8). The per-build cache from BP-900g-8-i already analysed each file once per pass, but one analysis walked its tree seven times (parent annotation plus six detectors) and rebuilt its scope's assignment map, module rescan included, for every Call/BinOp/Assign it evaluated. build_referential_integrity_closure_eval.py gains _tree_nodes (one ast.walk per tree, same breadth-first order) and _scope_assignments (one map per scope; a function's map is the module map overlaid with its own). The six detectors in _closure and _resolvers use them. A pass over all 407 real roots gave byte-identical closures and the same 226 WARNING lines before and after. Measured on a loaded host (load average 14 on 8 cores): guard CPU 12.3-12.7 s before vs 6.4-8.9 s after, in-process and interleaved; a fresh-consumer build.py into a docs/ + project.txt fixture took 32.9 s CPU (66.5 s wall) before vs 23.6 s CPU (25.3 s wall) after, back to back. New test unit_tests/test_bp_900g_8_iv.py (red before: 7 walks per tree, 6-9 map builds per scope, wrappers absent)."
adrs: []
commits: []
breaking: false
---

## Entry
