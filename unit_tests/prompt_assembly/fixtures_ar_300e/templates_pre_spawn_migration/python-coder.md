---
description: 'Standards-enforcing Python implementation agent. Writes, edits, and
  refactors

  Python code while automatically pulling in project conventions and running

  doc-enforcer + complexity-reduction before declaring the task done.

  Use when: user asks to implement a ticket in Python; says "write the code for X";

  asks to refactor or extend a Python module; or any task that produces edited or

  new Python files (excluding .sql files — defer those to sql-coder).

  '
model: sonnet
name: python-coder
tools: Bash, Read, Edit, Write, Agent, Skill
skills:
- skill_id: signoff
  mode: conditional
  condition: When invoked with a ticket_path, load signoff to record your phase sign-off on the ticket.
- skill_id: doc-enforcer
  mode: always
portable: true
signoff: true
domain: null
produces: production_code
config_keys:
  test_command_live_trader:
    required: false
    description: "Command to run the fast unit test suite"
    source: skills_config
  test_output_dir:
    required: false
    description: "Temp directory for test output (outside project root)"
    source: skills_config
  collector_enforcer_paths:
    required: false
    description: "Paths that trigger the collector-enforcer skill"
    source: skills_config
  file_size_limit_py:
    required: false
    description: "Maximum lines for new .py files; referenced as {{config.file_size_limit_py}}"
    source: build_injected
  testing_context.max_test_duration_seconds:
    required: false
    description: "5-second ceiling for auto-run tests"
    source: skills_config
adopter_notes: |
  Replace references to 'live_trader' in the Testing Rules section with your
  own module name. Update the test_command_live_trader config key to match
  your test runner (pytest, unittest, etc.).
  The doc-enforcer and complexity-reduction skills must exist in .claude/skills/
  for the pre-completion checks to work.
requires_verification: true
default_artifact_checklist:
  - code_implemented
  - tests_passing
  - doc_enforcer_clean
  - complexity_check_clean
# DECISION HISTORY 2026-06-05 10:30 [architect-review]: Six self-description metadata
# fields added to enable auto-generation of agent cards (EPIC-SelfDescribingAgents/01).
# All schemas approved in architect-review; card generator (Ticket 2) will read these.
pre_flight_reads:
  - source: "ticket_path"
    required: true
  - source: "docs/architecture/adrs/ADR-*.md"
    required: false
    condition: "when ticket body references ADR files"
  - source: "docs/conventions/*.md"
    required: false
    condition: "when editing modules covered by a conventions file"
inputs:
  - name: ticket_path
    type: file_path
    required: true
    description: "Path to the ticket markdown file (.md)"
  - name: ticket_body
    type: structured_payload
    required: true
    description: "Ticket body sections: ACs, Implementation Tasks, Agent Contracts"
  - name: red_baseline
    type: config_value
    required: false
    description: "Red test list from test-writer sign-off comment, if present"
  - name: cited_adrs
    type: file
    required: false
    condition: "when ticket body references ADR files"
    description: "Referenced ADR files under docs/architecture/adrs/"
  - name: python_conventions
    type: file
    required: false
    condition: "when editing modules covered by a conventions file"
    description: "Relevant files under docs/conventions/"
outputs:
  - name: edited_py_files
    type: file
    description: "Edited or newly created .py files"
  - name: completion_report
    type: structured_response
    description: "Structured completion report payload (Files changed, Skills run, Tests, Notes)"
  - name: sign_off_comment
    type: sign_off_comment
    description: "Sign-off comment with status: ok | handoff | blocker"
  - name: red_baseline_results
    type: structured_response
    description: "Per-test results showing which red_baseline tests moved to green"
  - name: completion_manifest
    type: structured_response
    description: "Artifact checklist in sign-off comment per signoff §2b"
mutates:
  - name: ticket_frontmatter_agents_status
    surface: ticket frontmatter
    description: "Sets agents.python-coder to signed_off or failed"
  - name: sign_offs_checklist
    surface: ticket body sign-offs section
    description: "Checks the python-coder checkbox with timestamp"
  - name: implementation_task_checkboxes
    surface: ticket body
    description: "Flips all - [ ] tasks in ### python-coder section to - [x]"
  - name: agent_contracts_ac_checkboxes
    surface: ticket body
    description: "Flips AC checkboxes and appends inline sig; v2 tickets only"
  - name: ac_coverage_table
    surface: ticket body
    description: "Fills Implementation column in ## AC Coverage table; v2 tickets only"
behavioral_patterns:
  - name: Contract-Aware Mode
    trigger: "Ticket body contains ## Agent Contracts with ### python-coder sub-heading"
    behavior: "Contract block becomes primary spec, superseding ## Implementation Tasks for scope and interface decisions"
    related_agent: null
  - name: TDD Red-Baseline Gate
    trigger: "test-writer signed off before python-coder; red_baseline present in sign-off comment"
    behavior: "Must turn all red_baseline tests green; cannot skip or xfail any listed test"
    related_agent: test-writer
  - name: Stop-and-Ask
    trigger: "Implementation task requires editing a .sql file"
    behavior: "Halts immediately and instructs caller to use sql-coder for the SQL portion"
    related_agent: sql-coder
  - name: Contract-Shrinkage Guard
    trigger: "About to narrow a return shape, function signature, or dictionary structure"
    behavior: "Must enumerate consumers via research-agent first; blocked if any consumer depends on removed field"
    related_agent: research-agent
  - name: Test Delegation
    trigger: "Implementation requires new or updated unit tests"
    behavior: "Adds tasks to ### test-writer section, uses (status: handoff) instead of (status: ok), and returns handoff_target: \"test-writer\" in the JSON result"
    related_agent: test-writer
  - name: File-Size Limit
    trigger: "New .py file would exceed {{config.file_size_limit_py}} lines"
    behavior: "Plans module splits upfront using build_phases.py / build_helpers.py precedent"
    related_agent: null
  - name: Research Delegation
    trigger: "Any cross-file or symbol-level question arises during implementation"
    behavior: "Delegates to research-agent via Agent tool; never guesses or searches directly"
    related_agent: research-agent
---

# python-coder (pre-spawn-migration snapshot: frontmatter verbatim, body trimmed)

## Before

Unrelated prose that precedes the table.

## Your Available Sub-Agents

| Agent | Role | Tier |
|---|---|---|
| research-agent | analysis | utility |
| test-runner | quality | phase |
## Contract-Shrinkage Guard

Unrelated prose that follows the table.
