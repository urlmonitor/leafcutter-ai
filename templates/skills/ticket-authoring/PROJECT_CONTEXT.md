# Project Context — ticket-authoring

## ADR Trigger Rule (KI-2)

Set `requires_adr: true` on any ticket that modifies:

1. The ticket-supervisor's phase-agent dispatch loop or status-tag routing
2. The signoff skill's format, status enum, or validation rules
3. The building-epics skill's supervisory actions or retry caps
4. Any agent template's contract with its supervisor (comment format, completion_manifest schema, required frontmatter fields)

These surfaces form the agent-supervisor contract. Changes here affect every downstream agent and should be recorded as architecture decisions.

Source: EPIC-CompletionManifestSignoff retrospective (2026-05-29).
