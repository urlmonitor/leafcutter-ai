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

**Correction (2026-08-26, 11:20 entry, and see BO-1000c-1a's own amended_by):**
the title and summary above claim the harness "unblocks" BO-1000c-1a's four
dispatch-based tests. An independent adversarial review found this false by
direct execution: all four pass unchanged against the PRE-vm harness too —
only BP-1100b-4's own three harness-fidelity tests were ever red against it.
The dependency was real for the ORIGINAL per-step-journal-file test_spec that
BO-1000c-1a's 2026-08-18 redefinition deleted; once the criterion moved onto
agent-dispatch capture, the dependency evaporated and nobody re-derived the
gate before flipping work_status to done. BO-1000c-1a has since reverted to
`work_status: in_progress`. The rest of this entry's factual claims about the
sandbox (denies require/module/exports/process/__dirname/__filename; the
zero-records calibration; the 461→468 suite delta at the time) are accurate
and stand — only the causal "unblocks" framing is wrong. See the 11:20 entry
in this same changelogs/ directory for the fuller correction, including two
further defects (an escapable sandbox and silently-lost strict mode) found
in the same review.
