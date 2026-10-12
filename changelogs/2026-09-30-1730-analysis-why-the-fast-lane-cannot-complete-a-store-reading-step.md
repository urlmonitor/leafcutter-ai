---
title: "Analysis: why the fast lane cannot complete a store-reading step"
date: "2026-09-30"
time: "17:30"
type: manual
components: 
  - build_orchestration
  - ac_store
summary: "Four-part analysis of the fast-lane claim failure, written so the work can be specified as acceptance criteria before any code changes. Nothing implemented."
description: "The fast lane halted on TQ-600a-3 and the failure was initially read two ways, both wrong. It does not hang: claim completes in 270.72 seconds and is SIGKILLed at 120 seconds by the agent harness default Bash timeout, since fast-lane-ship.js carries no budget of its own, proven by re-running with an explicit 600 second cap. And the resolver did not wrongly drag in finished work: TQ-600a-1 reads work_status todo on disk and on origin main, because PR 941 added seven implemented_by entries and never touched work_status, so the resolver correctly classified it as an unmet prerequisite and the store was what lied. The measured cause is that cProfile puts 98.8 percent of runtime inside yaml.safe_load, using the pure-Python loader while libyaml is installed and available, over a store walked twice because filter_already_claimed and claim_build_set each build their own index and neither shares. Cost is linear in bytes rather than quadratic, with bytes growing 3.83x against time growing 4.19x where quadratic predicts 14.7x, measured across six roots spanning 6 to 4458 records. Three of five hypotheses are refuted with evidence including the cycle-without-visited-set theory, since the traversal does carry a seen set and the known dependency cycles cannot cause this. Two findings beyond the brief are recorded: mark_done really is order ids times records because verify_done_eligible rebuilds the full status map per id, costing roughly nine minutes of parsing on a two-AC set before pytest starts, and the workflow reports a SIGKILL as the performer refusing, which is why the failure took a measurement rather than a read to diagnose. The phantom-todo is the more consequential half: a merged, tested and documented AC still reading todo has no guard, since check_done_proof only catches the opposite direction. Six fix directions are given with sizes and risks, from a ten-line CSafeLoader change through a line-scan approach measured at 343x, but none is implemented and none has acceptance criteria yet."
---

## Entry
