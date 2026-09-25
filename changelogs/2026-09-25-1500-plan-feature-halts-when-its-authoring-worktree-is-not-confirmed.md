---
title: "/plan-feature halts when its authoring worktree is not confirmed, and can pause again"
date: "2026-09-25"
time: "15:00"
type: manual
components:
  - build_orchestration
summary: "/plan-feature no longer carries on when setting up its authoring worktree fails. A refusal, an unreadable reply, a success-shaped reply naming no directory, or a silent reply naming neither directory nor branch now halts the run before any authoring agent runs, and the halt says which of the four it was. Previously the run continued with no worktree and the product-owner wrote AC files straight into the caller's own checkout. The setup-script lookup and the pause/resume steps also moved from status-checker, which refused them as outside its role, to worktree-agent, so a run can pause at a gate and be resumed instead of ending pause_persist_failed."
description: "Covers BO-1500a-5-i and BO-2300a-1-ii. Root cause of the first: the Pre-Stage-0 bootstrap halted only on an explicit non-zero exit_code and swallowed the JSON parse failure, so authoringWorktreePath stayed null. Root cause of the second: those dispatches went to status-checker (permits_shell: false), whose ticket-state charter makes it refuse generic shell work; worktree-agent is the only agent with permits_shell: true. Both were hit live on 2026-09-25 in run wf_734389cf-248. The shared E2 test harness gains a plan-feature default for the worktree-setup step (unit_tests/_plan_feature_harness_defaults.py) because its generic stub was itself one of the four failure shapes; 36 tests had been passing through the fail-open path. The same pause-store dispatch in finalize-feature.js is a known residual."
commits:
  - b64b8d9f
breaking: false
---

## Entry

`/plan-feature` could not tell a failed worktree setup from a successful one.
When the step that locates the worktree-setup script was refused, the fallback
got back a file path instead of the setup result, the parse failure was
swallowed, and the run went on with no authoring worktree. Triage then looked
for the AC store in the wrong directory and the product-owner wrote its files
into the caller's own checkout.

The bootstrap now halts before any authoring agent runs unless the setup step
positively names a worktree. Each of the four non-confirming shapes is reported
by name (`setup_failure_kind`: `refused`, `uninterpretable`,
`no_workspace_named`, `silent_success`).

Pausing at a gate was also broken: the pause record was written and read by
`status-checker`, which refuses shell work outside its ticket-state role. Those
dispatches, and the setup-script lookup, now go to `worktree-agent`.
