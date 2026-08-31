---
title: "The harness never unblocked what it claimed to, and its sandbox was escapable -- both found by independent review and fixed"
date: "2026-08-26"
time: "11:20"
type: manual
components: 
  - build_pipeline
  - build_orchestration
summary: "An adversarial review found the vm sandbox was escapable to a real process and file write, strict mode was silently lost, the four BO-1000c-1a tests never actually depended on the harness, and their coverage tolerated losing two-thirds of its signal. All five are fixed; BO-1000c-1a reverts to in_progress since its central in-flight-visibility clause still has zero coverage."
description: "Two high-severity defects were found by direct execution against the vm-sandboxed harness landed earlier this branch. vm.createContext() on a plain object literal left the sandboxed body's globalThis prototype-chained to the driver realm, so globalThis.constructor.constructor (and sibling routes through __proto__, object literals, and the AsyncFunction/GeneratorFunction constructors) yielded a live Function constructor that compiled in the driver realm -- reachable enough to append a real line to a real file on disk, the exact outcome the harness's own calibration test exists to certify impossible. Fixed with Object.setPrototypeOf(sandbox, null) before vm.createContext(), verified closed for every named route plus the exact file-write scenario. Separately, the body now compiles as its own source unit with no directive prologue, so it silently ran in sloppy mode where the prior harness ran strict -- an undeclared assignment created an implicit global instead of throwing, invisible to a line-level deletion audit since no line was deleted to cause it. Fixed by restoring an explicit strict-mode directive. A third, independent finding undercut the branch's own headline claim: the four BO-1000c-1a tests advertised as unblocked by the harness pass unchanged against the pre-vm harness too, and the four tests' own coverage was proven tautological by mutation -- suppressing two of three step-completion tags left every assertion green because the expected set was derived from the same run being checked. Both are fixed: the enumeration test for the sandbox's namespace now diffs against a freshly measured empty-context baseline instead of a hand-typed list, and the four coverage tests now compare against an independently pinned expectation via one shared, non-tautological helper, verified against the review's own mutation. Because the harness dependency was never real for the current tests, BO-1000c-1a reverts to in_progress -- its actual central clause, that a run's progress is readable while still in flight rather than only after it ends, has no executed coverage at any level and the test file says so itself. BP-1100b-4 remains done: its own harness-fidelity criteria are now genuinely met, independent of the BO-1000c-1a claim that turned out not to hold."
commits: []
breaking: false
---

## Entry
