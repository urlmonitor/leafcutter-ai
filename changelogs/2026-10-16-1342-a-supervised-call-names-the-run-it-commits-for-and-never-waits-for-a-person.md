---
title: A supervised call names the run it commits for and never waits for a person
date: "2026-10-16"
time: "13:42"
type: manual
components: 
  - build_orchestration
  - git_vcs_operations
summary: "Fast-lane delivery of 'A supervised call names the run it commits for and never waits for a person'."
description: "Fast-lane build of BO-4500a-4-iv (branch fast-lane/bo-4500a-4-iv). Built acceptance criteria: BO-4500a-4-iv. Adds --supervised with --run / --ac-id to the shared commit step: a supervised call must name the run or criterion it commits for (refused with policy_unattributed_supervised_call otherwise), echoes it in the answer's run and ac_id keys, and runs the checks with no terminal input, ending a check that stays silent past input_wait_limit_seconds (config/commit_step.json, 60) as hook_failed / check_awaited_input. Files modified: templates/scripts/commit_changes.py, templates/scripts/commit_step_base.py, templates/scripts/commit_step_config.py, config/commit_step.json, config/commit_step.schema.json."
breaking: false
---

## Entry
