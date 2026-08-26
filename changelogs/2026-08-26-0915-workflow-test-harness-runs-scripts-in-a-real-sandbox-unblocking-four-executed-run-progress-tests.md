---
title: "Workflow test harness runs scripts in a real sandbox, unblocking four executed run-progress tests"
date: "2026-08-26"
time: "09:15"
type: manual
components: 
  - build_pipeline
  - build_orchestration
summary: "run_workflow_under_e2() now executes workflow bodies inside a Node vm context exposing only the engine-injected globals, and the four dispatch-based tests it unblocks for BO-1000c-1a are implemented."
description: "BP-1100b-4 replaces the workflow test harness's plain Node.js execution with a vm.createContext() sandbox exposing exactly the globals the real E2 engine injects, so require, module, exports, process, __dirname and __filename all throw ReferenceError from a workflow body under test, matching production. A new test file proves the six denials by execution, plus a calibration test showing a filesystem-dependent journal write now produces zero records under the harness, where it previously produced one. With the harness engine-faithful, the remaining four test_spec descriptors on BO-1000c-1a are implemented: they run the real finalize-feature.js under the harness and assert on its agent-dispatch capture -- every reached step has a dispatch, dispatches appear in step order, they remain readable after the subprocess exits, and renaming the internal narrate helper leaves coverage unchanged. The full unit_tests/workflows/ suite was 461 passed before this change and is 468 passed after, so no other workflow test relied on a global the real engine does not provide. Both ACs are flipped to done with their covered_by lists updated."
commits: []
breaking: false
---

## Entry
