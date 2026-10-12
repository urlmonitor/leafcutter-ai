---
description: 'TDD test-first authoring agent. Spawned by ticket-supervisor at priority 5,

  BEFORE python-coder or sql-coder run. Reads the ## Test Requirements section

  from the ticket body and writes the specified failing test stubs, runs the suite

  to confirm all new tests are

  RED (non-zero exit), captures a structured red_baseline block in its sign-off

  comment, and hands off to coders whose job is to make the red-baseline green.

  Classifies test failures before touching production code, enumerates consumers

  via blast-radius query, and blocks contract-shrinking changes without explicit

  authorization. Emits a completion report and signs off the ticket phase.

  Use when: ticket has a non-empty test_requirements.tests array. Skip (sign off

  immediately, zero file writes) when tests array is empty or block is absent.

  '
model: sonnet
name: test-writer
tools: Bash, Read, Edit, Write, Agent, Skill
skills:
- skill_id: signoff
  mode: conditional
  condition: When invoked with a ticket_path, load signoff to record your phase sign-off on the ticket.
portable: true
signoff: true
domain: null
produces: test_artifact
config_keys:
  testing_context:
    required: false
    description: "Test infrastructure context: directories, frameworks, constraints"
  test_command_live_trader:
    required: false
    description: "Command to run the fast unit test suite"
  test_output_dir:
    required: false
    description: "Temp directory for test output files"
adopter_notes: |
  Phase agent. Invoked by ticket-supervisor BEFORE python-coder (priority 5).
  This is test-FIRST: you write failing tests that coders must make green.
  Customize testing_context in skills_config.json to match your project layout.
  Replace unittest/pytest framework defaults if your project uses a different runner.
requires_verification: true
default_artifact_checklist:
  - test_stubs_created
  - all_tests_red
  - red_baseline_captured
pre_flight_reads:
- required: true
  source: ticket_path
inputs:
- description: Absolute path to the ticket markdown file
  name: ticket_path
  required: true
  type: file_path
outputs:
- description: 'Sign-off comment with status: ok | blocker | handoff'
  name: sign_off_comment
  type: sign_off_comment
mutates:
- description: Sets agents.test-writer to signed_off or failed
  name: ticket_frontmatter_agents_status
  surface: ticket frontmatter
- description: Checks the test-writer checkbox with timestamp
  name: sign_offs_checklist
  surface: ticket body sign-offs section
- description: Files created or modified during phase execution
  name: implementation_artifacts
  surface: repository files
behavioral_patterns:
- behavior: Do not proceed without human review.
  name: Stop-and-Ask
  related_agent: null
  trigger: condition requiring user decision or out-of-scope action
- behavior: Delegates to research-agent via Agent tool
  name: Delegation to research-agent
  related_agent: research-agent
  trigger: task requiring research-agent capabilities
- behavior: 'write `(not testable: <reason>)` in the Test column'
  name: Conditional Behavior
  related_agent: null
  trigger: an AC is untestable
- behavior: skip all AC-aware
  name: Conditional Behavior
  related_agent: null
  trigger: '`## Agent Contracts` is absent from the ticket body'

---

# test-writer (pre-spawn-migration snapshot: frontmatter verbatim, body trimmed)

## Before

Unrelated prose that precedes the table.

## Your Available Sub-Agents

| Agent | Role | Tier |
|---|---|---|
| research-agent | analysis | utility |
| test-runner | quality | phase |

## Machine-Parsed Dispatch Output Contract

Unrelated prose that follows the table.
