---
description: 'Portable guided installation wizard. Auto-discovers the repo structure,
  fans out onboard-config-section Haiku sub-agents per config section, assembles a
  proposed skills_config.json, presents a diff for sign-off, and runs build.py on
  approval. Invoked via /onboard or auto-fired on SessionStart when skills_config.json
  is absent or all values are defaults.'
model: sonnet
name: onboard
tools: Bash, Read, Write, Edit, Agent
portable: true
signoff: false
domain: null
produces: analysis
config_keys: {}
adopter_notes: |
  Portable install wizard. Invoke via /onboard on a fresh repo after running
  build.py --target-dir . for the first time. This agent fills skills_config.json
  with project-specific values by auto-discovering the repo structure.
  NOT the same as a project-local onboarding-agent (which is project-specific).
spawn_allowlist:
  - onboard-config-section
requires_verification: true
pre_flight_reads:
- required: true
  source: ticket_path
inputs: []
outputs:
- description: Structured completion payload or sign-off comment
  name: completion_report
  type: structured_response
mutates:
- description: Read-only agent — no filesystem mutations
  name: none
  surface: none
behavioral_patterns:
- behavior: halt and surface the error.
  name: Stop-and-Ask
  related_agent: null
  trigger: condition requiring user decision or out-of-scope action
- behavior: halt and surface the full output.
  name: Stop-and-Ask
  related_agent: null
  trigger: condition requiring user decision or out-of-scope action
- behavior: 'surface a PREREQUISITE warning:'
  name: Conditional Behavior
  related_agent: null
  trigger: the auto-set fails for any reason
- behavior: 'set `optional_skills: []`'
  name: Conditional Behavior
  related_agent: null
  trigger: the user skipped the skill

---

# onboard (pre-spawn-migration snapshot: frontmatter verbatim, body trimmed)

Unrelated body prose.
