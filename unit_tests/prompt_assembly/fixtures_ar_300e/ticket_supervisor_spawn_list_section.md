### Spawn Allowlist (is_ticket_phase agents)

The following agents may be spawned via the Agent tool. Every agent name that
appears in a ticket's `agents:` map must be in this list (validated against
`leafcutter/config/agent_registry.json` when present):

```
adr-author
architect-review
architecture-diagram-author
brainstorm-lead
change-scope-reviewer
commit
documentation-expert
explanation-author
frontend-coder
how-to-author
pr-reviewer
pull-request
python-coder
reference-author
sql-coder
sql-query
status-checker
test-runner
test-writer
user-surface-smoker
```

Source of truth: `leafcutter/config/agent_registry.json` (`is_ticket_phase: true` entries).
Validation: if an agent name in the ticket's `agents:` map is NOT in this list and the
registry file does not exist, log a warning and attempt to spawn (backward-compatible
fallback). If the registry IS present and the name is absent, block with a structured
payload (see Agent Name Validation above).

{{project_paths_table}}
