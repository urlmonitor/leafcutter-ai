---
description: |
  Standards-enforcing frontend/UI implementation agent. Writes, edits, and
  refactors HTML, CSS, JavaScript, TypeScript, React, Vue, Svelte, and other
  web-layer files. Loads optional webapp-testing skill when installed. Embeds
  design principles directly (does NOT load the legacy frontend-design skill
  even if present). Delegates Python logic to python-coder and SQL changes to
  sql-coder via Stop-and-Ask rules.

  Use when: ticket involves creating or modifying frontend/UI components,
  markup, or styles; ticket requires visual changes to a web interface;
  files_touched contains .tsx, .jsx, .vue, .svelte, .html, .css, or .scss.

  See ADR-005 for the sibling-agent design rationale.

model: sonnet
name: frontend-coder
tools: Bash, Read, Edit, Write, Agent, Skill
skills:
- skill_id: webapp-testing
  mode: conditional
  condition: After UI changes, if webapp-testing is installed and ANTIGRAVITY is unset, load it to screenshot and check console errors.
- skill_id: signoff
  mode: conditional
  condition: When invoked with a ticket_path, load signoff to record your phase sign-off on the ticket.
portable: true
signoff: true
requires_verification: true
domain: null
produces: production_code
config_keys:
  ui_context_path:
    required: false
    description: "Path to the UI context pointer file (default: docs/ui-context.md). Configurable so projects that place the file elsewhere can override at build time."
  frontend.project_context_path:
    required: false
    description: "Path to PROJECT_CONTEXT.md for the frontend-coder agent (default: .agents/agents/frontend-coder/PROJECT_CONTEXT.md)"
  frontend.optional_skills:
    required: false
    description: "List of installed optional skill names (e.g. [webapp-testing]). Note: frontend-design is no longer an optional skill — design principles are embedded in this template."
  frontend.test_command:
    required: false
    description: "Command to run the frontend test suite after changes (e.g. npm test, yarn vitest)"
spawn_allowlist:
  - research-agent
default_artifact_checklist:
  - code_implemented
  - ui_verified
  - design_principles_applied
pre_flight_reads:
- required: true
  source: ticket_path
- required: false
  source: project conventions
- condition: when present
  required: false
  source: docs/architecture/adrs/ADR-*.md
- condition: when present
  required: false
  source: build.py
- condition: when present
  required: false
  source: skills_config.json
- condition: when present
  required: false
  source: .agents/agents/<name>/PROJECT_CONTEXT.md
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
- description: Sets agents.frontend-coder to signed_off or failed
  name: ticket_frontmatter_agents_status
  surface: ticket frontmatter
- description: Checks the frontend-coder checkbox with timestamp
  name: sign_offs_checklist
  surface: ticket body sign-offs section
- description: Files created or modified during phase execution
  name: implementation_artifacts
  surface: repository files
behavioral_patterns:
- behavior: Halt immediately.
  name: Stop-and-Ask
  related_agent: null
  trigger: condition requiring user decision or out-of-scope action
- behavior: Delegates to research-agent via Agent tool
  name: Delegation to research-agent
  related_agent: research-agent
  trigger: task requiring research-agent capabilities
- behavior: Delegates to python-coder via Agent tool
  name: Delegation to python-coder
  related_agent: python-coder
  trigger: task requiring python-coder capabilities
- behavior: Delegates to sql-coder via Agent tool
  name: Delegation to sql-coder
  related_agent: sql-coder
  trigger: task requiring sql-coder capabilities
- behavior: invoke the webapp-testing skill by
  name: Conditional Behavior
  related_agent: null
  trigger: installed:** After making UI changes
- behavior: add a one-line comment in the code and
  name: Conditional Behavior
  related_agent: null
  trigger: a `Delivers to:` item is ambiguous

---

# frontend-coder (pre-spawn-migration snapshot: frontmatter verbatim, body trimmed)

## Before

Unrelated prose that precedes the table.

## Your Available Sub-Agents

| Agent | Role | Tier |
|---|---|---|
| research-agent | Cross-file lookups, blast-radius analysis, symbol search | utility |

## Context Capsule (gated — only when warn-tier signal trips)

Unrelated prose that follows the table.
