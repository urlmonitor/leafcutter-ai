---
title: Finalize-feature hardening — pre-flight, error reporting, and deploy-parity
  fixes
date: '2026-07-23'
time: 00:00
type: fix
components:
- build_pipeline
summary: Fixed finalize-feature pre-flight to accept string or object targets, emit
  actionable errors on unresolvable targets, and suppress false test-regression halts
  caused by deploy-state-only failures across five merged PRs.
description: '5 PRs (#379-#382, #385) across FIN-100g-2/-3/-4 and FIN-100c-4/-7/-9:
  (1) pre-flight accepts a bare string or {target}/{target_branch} object without
  crashing on .trim() (#379); (2) unresolvable target emits an error naming the target,
  expected forms, and git worktree list, with found:false handler ordered before the
  must-run-from-feature-branch abort (#380); (3) deploy-parity self-check runs before
  post-merge triage, dispatching step-3-deploy-parity and excluding only build-state-only
  failures, gated on postMergeFailures.length > 0 with a still-failing contradiction
  guard (#381, #385); (4) FIN-100c-4/-7/-9 behavioral tests backfilled and work_status
  reconciled to done (#382). Primary changed file: templates/workflows-js/finalize-feature.js.'
commits:
- a20ebebd7
- 745981c06
- a813ac3c3
- 724b5279d
- f8a0f53f6
breaking: false
created: '2026-07-23'
last_updated: '2026-07-23'
status: active
---
## Entry
