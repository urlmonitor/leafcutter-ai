---
title: "The shared commit step's answer keys and reason codes now come from a config file"
date: "2026-10-16"
time: "11:30"
type: manual
components: 
  - build_orchestration
  - git_vcs_operations
summary: "The shared commit step now gives one consistent answer whose wording is defined in a config file instead of in code, and refuses to run if that file is missing or invalid."
description: "BO-4500a-4: config/commit_step.json (with config/commit_step.schema.json) now holds answer_version, the 17 answer keys, the policy/step/check/nothing reason_code families and the retry ceilings; templates/scripts/commit_step_config.py loads and validates it, and a missing or invalid file is refused with step_config_unreadable. git_unavailable, git_error, commit_error and internal_error are retired in favour of step_vcs_error and step_index_locked. Adds test_bo4500a_4_one_answer_contract.py."
commits: 
  - 2f0e5cb17632351e94b383452574ce55c5477c9d
breaking: false
---

## Entry
