---
title: "feat(build): descriptive_only skills_invoked marker restores INF-600d-1 entries (PR #233)"
date: "2026-07-08"
time: "09:05"
type: manual
components: 
  - build_pipeline
  - agent_registry
  - skills_system
summary: "Added a descriptive_only marker that allows agents to declare intentional inline capabilities in skills_invoked without triggering the cross-reference validator, un-regressing the run-tests and direct-write entries while keeping the build green on all unmarked unresolvable skill IDs."
description: "1 squash commit (PR #233, feat(build)). Adds descriptive_only: true marker to the agent self-description schema. validate_agent_self_description and registry_validator.check_skills_invoked_xref skip entries carrying this marker while unmarked unresolvable skill_ids still hard-fail. Restores run-tests (python-coder) and direct-write (documentation-expert) to skills_invoked, un-regressing INF-600d-1."
pr: 233
commits: 
  - fc6d36b6
breaking: false
---

## Entry
