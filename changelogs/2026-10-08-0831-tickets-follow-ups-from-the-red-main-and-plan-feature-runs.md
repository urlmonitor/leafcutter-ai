---
title: "Tickets: follow-ups from the red main and plan-feature runs of 2026-10-06 to 2026-10-08"
date: "2026-10-08"
time: "08:31"
type: manual
components:
  - ux_prototyping
  - ac_driven_dev
  - build_orchestration
  - decision_kernel
  - infrastructure
  - commit_guardian
  - build_pipeline
summary: "Files nine tickets for defects seen between 2026-10-06 and 2026-10-08. One defect already had a known issue, so it gets a dated occurrence there instead. No code changes."
description: "New tickets in tickets/00_inbox, all dated 2026-10-08. PlanFeatureResumeKeepsItsClassification: a resumed plan-feature run asked the product-truth classifier again, got a different answer, and dropped the owner's edit at the mock-data gate. PlanFeatureSetupReplyCarriesOnlyThePayload: on a first run the setup agent relayed the whole bootstrap log and cut off the JSON reply. DecisionRecordBasisForHumanRuling: a human ruling is staged as a kernel ranking; the fix needs a re-reviewed, re-pinned decision schema. AnalysisRetrievalKeepsParentDesignDoc: the analysis folder outgrew the per-source cap and the parent design document is cut; this needs an ADR. Three Windows-only test failures, each with its own cause: HarvestUnreadableSinkTestRunsOnWindows (chmod cannot make a file unreadable on Windows), SinkParityMessagePrintsPathsVerbatim (repr doubles the backslashes in paths) and CommitGuardLocatorsFindCopyModeInstall (with copied shims the guard cannot find its resolver or the AC store). DoneProofLaunchesVitestOnWindows: the done-proof starts the POSIX vitest shim, which Windows rejects. BuildPipelineHygiene covers three fixes: the durations job lacks the web toolchain, two dead manifest helper copies remain, and copy shims bring a retired command back after a hand delete (the retirement step only removes what the manifest records). The product-truth generator writing CRLF was already known issue KI-BP-20260910-1240 and gets Occurrence 5. Two existing tickets get dated cross-links."
commits: []
---

## Entry

Nine new tickets record the defects found while main was red and while running plan-feature
between 2026-10-06 and 2026-10-08. Each ticket carries its evidence, the root cause where it
could be reproduced, and testable acceptance criteria.

- **Plan-feature, two tickets.**
  - A resumed run kept the classification of the run it resumes only by chance. When the
    classifier answered differently, the owner's answer was lost without a message.
  - A first run in a new project could halt because the setup agent relayed the whole bootstrap
    log.
- **Decision kernel, two tickets.**
  - A human ruling gets an honest assessment basis.
  - Retrieval over the analysis folder needs a decided rule, so the parent design document is
    not cut while its parts are offered.
- **Windows, four tickets.**
  - One test fixture.
  - One error message.
  - The commit guard's module lookup with copied shims.
  - Launching vitest for the done proof.
- **Build pipeline, one hygiene ticket.**
  - The durations job.
  - Dead helper copies.
  - Copy shims that bring a retired command back.

The product-truth generator's CRLF writes were already a known issue. They get a new dated
occurrence instead of a ticket.
