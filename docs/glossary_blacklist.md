---
title: Glossary Blacklist
description: Terms excluded from the project glossary, managed automatically by the
  check_glossary_coverage hook and glossary-triage agent to suppress false-positive
  jargon candidates.
type: reference
created: '2026-07-09'
last_updated: '2026-07-15'
status: active
components: []
---
# Glossary Blacklist

Terms in this table are excluded from the glossary. Managed automatically by
the glossary-automation system (`check_glossary_coverage.py` / `glossary-triage`).

| term | reason | added |
|------|--------|-------|
| check_file_size | Script filename in a code-block example (pre-commit entry path), not a domain concept | 2026-05-27 |
| tickets_inbox_path | JSON config field name in skills_config.json reference table, not a domain concept | 2026-05-27 |
| tickets_inbox_epics_path | JSON config field name in skills_config.json reference table, not a domain concept | 2026-05-27 |
| tickets_todo_path | JSON config field name in skills_config.json reference table, not a domain concept | 2026-05-27 |
| tickets_done_path | JSON config field name in skills_config.json reference table, not a domain concept | 2026-05-27 |
| tickets_rejected_path | JSON config field name in skills_config.json reference table, not a domain concept | 2026-05-27 |
| ticket_lifecycle_path | JSON config field name in skills_config.json reference table, not a domain concept | 2026-05-27 |
| test_command_live_trader | JSON config field name in skills_config.json reference table, not a domain concept | 2026-05-27 |
| test_command_sql | JSON config field name in skills_config.json reference table, not a domain concept | 2026-05-27 |
| test_command_single_file_pattern | JSON config field name in skills_config.json reference table, not a domain concept | 2026-05-27 |
| changelog_categories_path | JSON config field name in skills_config.json reference table, not a domain concept | 2026-05-27 |
| precommit_autofix_config_path | JSON config field name in skills_config.json reference table, not a domain concept | 2026-05-27 |
| test_output_dir | JSON config field name in skills_config.json reference table, not a domain concept | 2026-05-27 |
| worktree_base_path | JSON config field name in skills_config.json reference table, not a domain concept | 2026-05-27 |
| kill_residual_processes | JSON config field name (worktree_cleanup sub-field), not a domain concept | 2026-05-27 |
| sql_test_results | Filename fragment in a log glob pattern example, not a domain concept | 2026-05-27 |
| collector_enforcer_paths | JSON config field name in skills_config.json reference table, not a domain concept | 2026-05-27 |
| top_level_packages | JSON config field name in skills_config.json reference table, not a domain concept | 2026-05-27 |
| additionalProperties | JSON Schema keyword, not a project domain concept | 2026-05-27 |
| setUp | Python unittest method name, not a domain concept | 2026-05-27 |
| tearDown | Python unittest method name, not a domain concept | 2026-05-27 |
| max_test_duration_seconds | JSON config field name (testing_context sub-field), not a domain concept | 2026-05-27 |
| manual_test_suffix | JSON config field name (testing_context sub-field), not a domain concept | 2026-05-27 |
| db_connection_test | JSON config field name (testing_context sub-field), not a domain concept | 2026-05-27 |
| test_output_rules | JSON config field name (testing_context sub-field), not a domain concept | 2026-05-27 |
| agent_delivery_workflows | Document filename used as a cross-link path in frontmatter and prose, not a standalone domain concept | 2026-06-03 |
| scan_ac_store | Python script filename (code identifier), not a standalone domain concept | 2026-06-05 |
| generate_ticket_from_ac | Python script filename (code identifier), not a standalone domain concept | 2026-06-05 |
| classDef | Mermaid CSS class definition syntax keyword, not a domain concept | 2026-06-05 |
| nInputs | Mermaid \n-escape tokenization artifact, not a domain concept | 2026-06-05 |
| nOutputs | Mermaid \n-escape tokenization artifact, not a domain concept | 2026-06-05 |
| nExit | Mermaid \n-escape tokenization artifact, not a domain concept | 2026-06-05 |
| nIdempotency | Mermaid \n-escape tokenization artifact, not a domain concept | 2026-06-05 |
| nFrontmatter | Mermaid \n-escape tokenization artifact, not a domain concept | 2026-06-05 |
| nBody | Mermaid \n-escape tokenization artifact, not a domain concept | 2026-06-05 |
| nSource | Mermaid \n-escape tokenization artifact, not a domain concept | 2026-06-05 |
| nNo | Mermaid \n-escape tokenization artifact, not a domain concept | 2026-06-05 |
| mark_ac_done | Internal script filename (scripts/ac_store/mark_ac_done.py), not a domain concept | 2026-06-05 |
| build_ac_mode_detection | Internal script filename (scripts/ac_store/build_ac_mode_detection.py), not a standalone domain concept | 2026-06-17 |
| goal_to_epic | Internal script filename (scripts/ac_store/goal_to_epic.py), not a standalone domain concept | 2026-06-17 |
| check_exception_handling | Script filename (templates/commit-guardian/check_exception_handling.py), not a domain concept | 2026-06-17 |
| validate_ac_schema | Internal script filename (scripts/ac_store/validate_ac_schema.py), not a domain concept | 2026-06-05 |
| sequenceDiagram | Mermaid diagram-type keyword in a code block, not a domain concept | 2026-06-05 |
| stateDiagram | Mermaid diagram-type keyword in a code block, not a domain concept | 2026-06-05 |
| nBuild | Mermaid \n-escape tokenization artifact, not a domain concept | 2026-06-05 |
| nBlocks | Mermaid \n-escape tokenization artifact, not a domain concept | 2026-06-05 |
| nEnforces | Mermaid \n-escape tokenization artifact, not a domain concept | 2026-06-05 |
| nIdempotent | Mermaid \n-escape tokenization artifact, not a domain concept | 2026-06-05 |
| nReads | Mermaid \n-escape tokenization artifact, not a domain concept | 2026-06-05 |
| nRequires | Mermaid \n-escape tokenization artifact, not a domain concept | 2026-06-05 |
| nReturns | Mermaid \n-escape tokenization artifact, not a domain concept | 2026-06-05 |
| nSequences | Mermaid \n-escape tokenization artifact, not a domain concept | 2026-06-05 |
| nSets | Mermaid \n-escape tokenization artifact, not a domain concept | 2026-06-05 |
| nSort | Mermaid \n-escape tokenization artifact, not a domain concept | 2026-06-05 |
| nWrites | Mermaid \n-escape tokenization artifact, not a domain concept | 2026-06-05 |
| agentType | JavaScript named parameter in agent() call syntax, not a standalone domain concept | 2026-07-09 |
| phaseName | JavaScript named parameter placeholder in agent() call syntax, not a standalone domain concept | 2026-07-09 |
| clean_stale_artifacts | Python function name in build_phases.py (code identifier), not a domain concept | 2026-07-15 |
| change_target_triggers | YAML config key in documentation_gates section of guardrail_gates.yaml, not a standalone domain concept | 2026-07-21 |
| risk_surface_triggers | YAML config key in documentation_gates section of guardrail_gates.yaml, not a standalone domain concept | 2026-07-21 |
| non_triggering_classifications | YAML config key in documentation_gates section of guardrail_gates.yaml, not a standalone domain concept | 2026-07-21 |
| build_placeholder_detection | Python script filename (scripts/build_placeholder_detection.py), not a standalone domain concept | 2026-07-21 |
| target_doc_path | Pipe-delimited field name within Agent Contracts block example (code-level field), not a domain concept | 2026-07-21 |
| flow_change_gates | YAML config section name in guardrail_gates.yaml (code-level identifier), not a standalone domain concept | 2026-07-21 |
| surgical_removal_guard | YAML config section name in guardrail_gates.yaml (code-level identifier), not a standalone domain concept | 2026-07-21 |
| DOC_EXPERT_SINGLE_INJECTION | Named invariant ID constant in guardrail_gates.yaml surgical_removal_guard, not a domain concept | 2026-07-21 |
