---
title: "Resolving a fast-lane build set no longer re-reads the whole AC store on every step"
date: "2026-08-24"
time: "21:40"
type: manual
components: 
  - build_orchestration
  - ac_store
summary: "The resolver parses the AC store once per run instead of once per traversal, cutting a one-criterion resolution from roughly three minutes to well under one."
description: "BO-2400c-6, -6-i and -6-ii. traverse_ac_tree built a complete id-to-record index by rglob-ing and YAML-parsing every file in the store on EVERY call, and resolve_connected_build_set had already built that index before calling it again — once for the subtree walk and once per not-done composite dependency expanded. A run therefore paid N+1 full parses of the whole store, never fewer than two. Measured against the real 3,232-file store, resolving a set of ONE criterion took 178.32 seconds. traverse_ac_tree now accepts an optional prebuilt id_index and walks it directly; the self-building path is unchanged for callers that hold no index, which is why goal_to_epic.py needed no edit. The same command now returns the identical single id in 27-39 seconds depending on machine load — a 4.5 to 6.5 times improvement, and both figures are recorded rather than just the better one. The correctness trap here mattered more than the speed. _drain_cycles mutates id_index in place, deleting cycle nodes, and the resolver calls it before the traversal. Handing the traversal that drained index — the obvious reading of pass the index you already have — would silently drop every subtree hanging off a cycle node: fewer ACs built, no exception, no warning, a phantom-done regression hidden inside a performance fix in the tool built to prevent phantom-done. The fix snapshots the index before the drain and gives the traversal that undrained view, while the dependency-closure walk keeps reading the drained one. Because the live store is currently acyclic, a guard written against real data would have passed while exercising nothing, so the covering test builds a fixture with a genuine cycle plus a leaf reachable only through a cycle member — its captured stderr shows the cycle warning firing, proving the drain path is actually taken. The improvement is asserted as a parse count, never a wall clock: a timing bound would flake on CI and be deleted by the first person it inconvenienced, and the reason is written into the criterion so it survives review. Residual, recorded in KI-BO-014 rather than glossed: one full parse still costs 30-40 seconds and is now the floor, so the cold start went from unusable to noticeable rather than to fast, and it still grows with store size."
commits: []
breaking: false
---

## Entry
