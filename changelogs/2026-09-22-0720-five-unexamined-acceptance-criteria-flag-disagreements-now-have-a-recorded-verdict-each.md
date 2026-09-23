---
title: "Five unexamined acceptance-criteria flag disagreements now have a recorded verdict each"
date: "2026-09-22"
time: "07:20"
type: manual
components: 
  - ac_store
summary: "Five acceptance criteria disagreed with an automated check about whether their work leaves a lasting change behind, and had been parked unexamined. Each now has a written verdict: three were wrong and should be corrected, two were right and the automated check is what needs fixing."
description: "Adds docs/analysis/2026-09-21-declares-side-effect-five-record-audit.md. Five records carry an authored declares_side_effect that disagrees with the value derived from their own Then clause, all parked in _KNOWN_PRE_EXISTING_DISAGREEMENTS so the staleness test stays green. The document records a per-record verdict: BO-2900g-1, BO-2900g-4 and BO-2900g-2-i assert the content of a produced structure and should flip to false; BO-2400g-4 and BO-2400g-4-i assert a genuine durable effect and should stay true, pinned, because the derivation under-reads them. The separating test is not whether a clause is phrased as an absence but whether a process that writes nothing can satisfy it, which is the test the two cited precedents were reconciled on. Also records the two deriver defects behind the false negatives, the template the three flips must follow including the CI trap that flipping without shrinking the allowlist fails the staleness test, and that the gate these flags route reads a fixture block the generator never emits. No AC record is modified."
breaking: false
---

## Entry
