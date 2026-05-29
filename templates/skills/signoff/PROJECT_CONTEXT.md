# Project Context — signoff

## ADR Trigger Rule

This skill is a contract surface between agents and their supervisor. Any change to the signoff format, status enum, completion_manifest schema, or validation rules must set `requires_adr: true` on the implementing ticket.

See `templates/skills/ticket-authoring/PROJECT_CONTEXT.md` for the full rule.

Source: EPIC-CompletionManifestSignoff retrospective (2026-05-29).
