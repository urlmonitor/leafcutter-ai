---
title: "The build ships the scripts and config files agents are told to use, so documentation-verifier no longer fails in consumer projects"
date: "2026-11-17"
time: "12:30"
type: manual
components:
  - build_pipeline
summary: "documentation-verifier's placeholder scan imported build_placeholder_detection from <worktree_root>/scripts, but the build never deployed that module, so in every consumer install the verifier failed closed with ModuleNotFoundError and blocked every ticket with that phase (seen in DIAGraph on v21.0.93, ticket INF-120c-3). The build now deploys build_placeholder_detection.py with build_placeholder_table_context.py, and the template imports it from {{config.output_root}}/scripts. The same sweep found four more files agents were told to use that never shipped: commit_classifier.py and commit_pattern_learner.py (commit agent, Step 2a) with their config/commit_message_patterns.json, and config/skills_config.default.json and config/test_requirements.schema.json (onboard, test-writer). All are now deployed and named by their deployed paths."
description: "BP-900b-5. Scripts added to AGENT_SUPPORT_SCRIPT_FILES (build_agent_support_scripts); config files added to the build_ac_store core-config deploy (commit_message_patterns.json also to both build.py manifest declarations, which the closure guard checks). Templates fixed: documentation-verifier, commit, onboard, test-writer. New test unit_tests/build_guards/test_bp_900b_5_prompt_references_deployed.py runs the verifier's exact scan command against the shared consumer-layout build and fails when any compiled prompt tells the agent to run, import or read a package file the install does not contain."
commits:
breaking: false
---

## Entry

In projects that install leafcutter, the documentation check could not load its own helper and
stopped every ticket that had a documentation check. The install now includes that helper, and
four other files agents were told to use but never received, so those steps run in every project.
