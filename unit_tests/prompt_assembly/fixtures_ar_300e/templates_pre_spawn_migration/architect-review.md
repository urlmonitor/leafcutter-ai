---
description: 'Structural impact gatekeeper for proposed changes. Receives a refined
  ticket

  from create-ticket, calls research-agent for blast-radius analysis, classifies

  impact as small or large using a documented rubric, and either writes an

  inline architectural note (Sonnet only) or escalates to an Opus sub-agent.

  (internal — invoked by parent agents only)

  '
model: sonnet
name: architect-review
tools: Bash, Read, Edit, Write, Agent, Skill
skills:
- skill_id: signoff
  mode: conditional
  condition: When invoked with a ticket_path, load signoff to record your phase sign-off on the ticket.
portable: true
signoff: true
domain: null
produces: review_verdict
config_keys: {}
adopter_notes: |
  Phase agent. Invoked by ticket-supervisor.
requires_verification: true
default_artifact_checklist:
  - blast_radius_assessed
  - impact_classified
  - architectural_note_written
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
- description: Sets agents.architect-review to signed_off or failed
  name: ticket_frontmatter_agents_status
  surface: ticket frontmatter
- description: Checks the architect-review checkbox with timestamp
  name: sign_offs_checklist
  surface: ticket body sign-offs section
- description: Files created or modified during phase execution
  name: implementation_artifacts
  surface: repository files
behavioral_patterns:
- behavior: Delegates to adr-author via Agent tool
  name: Delegation to adr-author
  related_agent: adr-author
  trigger: task requiring adr-author capabilities
- behavior: Delegates to architect-review-deep via Agent tool
  name: Delegation to architect-review-deep
  related_agent: architect-review-deep
  trigger: task requiring architect-review-deep capabilities
- behavior: new constraint, new cross-component contract) that is not already covered
    by an
  name: Conditional Behavior
  related_agent: null
  trigger: the change introduces a new cross-cutting policy decision (new abstraction
- behavior: 'also set `adr-author: needed` in the `agents` map'
  name: Conditional Behavior
  related_agent: null
  trigger: '`requires_adr: true`'

---

# architect-review (pre-spawn-migration snapshot: frontmatter verbatim, body trimmed)

## Before

Unrelated prose that precedes the table.

## Your Available Sub-Agents

| Agent | Role | Tier |
|---|---|---|
| research-agent | analysis | utility |

## Machine-Parsed Dispatch Output Contract

Unrelated prose that follows the table.
