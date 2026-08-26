---
title: "The finalize run-progress journal that never wrote a line is removed, and the tests that kept it green are replaced"
date: "2026-08-26"
time: "00:20"
type: manual
components: 
  - build_orchestration
  - build_pipeline
summary: "finalize-feature.js no longer carries a filesystem journal helper it could never execute, and BO-1000c-1a's ten presence-only tests are replaced by one absence guard."
description: "BO-1000c-1a was marked done while its mechanism had never once run. appendJournal() loaded Node's fs module through the CommonJS module loader, but the E2 engine injects only agent, parallel, pipeline, phase, log, args, workflow and budget into a workflow body — no module loader, per ADR-030. The require call threw on every invocation, a surrounding try/catch logged a WARNING, and the run reported success. The helper, its path variable and both call sites in narrate() and outcome() are removed, with the rationale left in place of the deleted code so it is not reintroduced. The criterion was redefined onto the journal the engine already writes per agent dispatch; that redefinition was authored on 2026-08-18 and had sat unmerged on an unpushed local branch for eight days. Two corrections were made while landing it: the title still described the deleted mechanism and contradicted its own amended criteria, and work_status stayed done though only one of five declared test descriptors is implemented here, so it is now in_progress. The coverage change is the point. All ten previous tests read the JavaScript as text and asserted that appendJournal, journalPath and fs.appendFileSync were present; all ten passed for the entire life of the defect because the strings were there and the code never ran. Nine of the ten fail against the corrected source, each demanding the dead mechanism be restored. They are replaced by a single absence assertion, which is the shape that works here: a presence assertion stays green on dead code, an absence assertion fails the moment the known-broken pattern returns, reached or not. The four executed dispatch-coverage tests in the redefined contract need a vm-sandboxed harness that does not yet exist on main and land with it."
commits: []
breaking: false
---

## Entry
