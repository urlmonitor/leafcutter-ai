---
title: "The shared commit step is split into three files, with no change in behaviour"
date: "2026-10-16"
time: "09:42"
type: manual
components: 
  - build_orchestration
  - git_vcs_operations
summary: "Reorganised the shared commit step into three smaller files to make room for upcoming work, with no change in how it behaves."
description: "Split templates/scripts/commit_changes.py (BO-4500) with no behaviour change, to make room for BO-4500a-4. New templates/scripts/commit_step_base.py holds StepRefusal, the answer builder, the git runners and the max_automated_fix_retries config read. New templates/scripts/commit_step_parents.py holds AC structural-parent resolution, including the fail-closed step_parent_resolver_unavailable refusal. Both deploy beside commit_changes.py via the existing templates/scripts/*.py glob. unit_tests/build_orchestration/test_bo4500a_1_ii_resolver_unavailable.py now copies the commit_step_*.py siblings into its isolated folder."
commits: 
  - dbd29ea4b
breaking: false
---

## Entry
