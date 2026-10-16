---
description: 'Haiku sub-agent spawned in parallel by the onboard wizard. Receives
  a discovery payload (folder structure, file excerpts, owned keys, confirmed values)
  and returns a JSON config fragment covering only the keys it owns. One instance is
  spawned per skills_config.json section (testing, packages, tickets, commands, project).'
model: haiku
name: onboard-config-section
tools: Read
portable: true
signoff: false
domain: null
produces: analysis
config_keys: {}
adopter_notes: |
  Haiku sub-agent spawned by the onboard wizard. Not invoked directly.
spawn_allowlist: []
pre_flight_reads:
- required: true
  source: ticket_path
inputs: []
outputs:
- description: 'Output field: key1'
  name: key1
  type: structured_response
- description: 'Output field: key2'
  name: key2
  type: structured_response
- description: 'Output field: test_command_live_trader'
  name: test_command_live_trader
  type: structured_response
mutates:
- description: Read-only agent — no filesystem mutations
  name: none
  surface: none
behavioral_patterns:
- behavior: '`01_todo/`, `99_done/` subdirs:'
  name: Conditional Behavior
  related_agent: null
  trigger: '`tickets/` folder found with `00_inbox/`'

---

# onboard-config-section (pre-spawn-migration snapshot: frontmatter verbatim, body trimmed)

Unrelated body prose.
