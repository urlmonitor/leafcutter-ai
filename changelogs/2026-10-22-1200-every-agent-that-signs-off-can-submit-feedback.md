---
title: "Every agent that signs off can submit feedback, and the build fails if one cannot (KI-FC-003)"
date: "2026-10-22"
time: "12:00"
type: manual
components: 
  - feedback_collector
  - build_pipeline
summary: "The build now checks that every agent with signoff: true can write to at least one feedback category, and fails naming all that cannot. Before, an agent left out of the writer lists had its feedback refused on every run with no signal, which happened to ac-validator and ac-fulfillment-gate. On its first run the check found two more agents, restructuring-specialist and change-scope-reviewer, which are now registered. A writer entry that names no registered agent is reported as a warning."
description: "New scripts/build_phases_feedback_writers.py (check_feedback_writers) is run from build.py _validate_all, so every build and --validate-only reach it. It reads the signoff field from each agent definition, the feedback categories file and the agent registry. It uses the new shared feedback_validation.writer_allowed predicate, which validate_writer now calls, so submission and the check cannot disagree. The hook sentinel is neither an unknown writer nor credited to any agent. A non-boolean signoff, malformed YAML or an unreadable file fails the build and names the file. Both copies of feedback_categories.yaml add restructuring-specialist and change-scope-reviewer to the six categories the AC gates use, and drop the comment advertising an [all_agents] sentinel that submission never implemented. ACs INF-100c-5 and -i..-v are done, and KI-FC-003 is resolved."
migration_steps:
  - "If the build names one of your own agents as signing off but able to write to no feedback category, add its id to allowed_writers of the categories it reports in (at least 'complete') in your feedback_categories.yaml, or set signoff: false if it does not sign off."
breaking: true
---

## Entry
