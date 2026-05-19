# leafcutter/config

## Purpose

Static configuration files for the leafcutter package. These files
are consumed at runtime by scripts and agents — they are NOT built into `.claude/`
and must NOT be edited by automated tools without a PR review.

## Key Files

| File | Purpose |
|------|---------|
| `agent_registry.json` | Single source of truth for all agents (id, tier, role, is_ticket_phase, spawn_allowlist, etc.) |
| `agent_registry.schema.json` | JSON Schema for agent_registry.json — validates entries on build |
| `diagram_types.json` | Canonical diagram_type values used by architect-review and architecture-diagram-author |
| `doc_types.json` | Canonical doc_type values (how_to, explanation, adr, etc.) used by documentation-expert |
| `feedback_categories.yaml` | Closed vocabulary for the feedback collection system (EPIC-FeedbackCollection). Seven starter categories with allowed_writers and default_severity. PR-gated — do not add/remove categories without a PR. |
| `package_boundary.json` | Lists project-specific module names used to classify files as portable vs. domain-specific (ADR-020). |
| `paths.json` | Canonical path constants injected into every built agent and skill template via build.py. |
| `skill_registry.json` | Registry of all skills in the package (id, template_path, description). |
| `skill_registry.schema.json` | JSON Schema for skill_registry.json. |
| `skills_config.default.json` | Default allowed-tools overrides for skills. |
| `skills_config.schema.json` | JSON Schema for skills_config. |
| `test_requirements.schema.json` | JSON Schema for the `test_requirements:` block in ticket frontmatter. |
| `ticket_lifecycle.json` | State machine for ticket status transitions. |

## Critical Context

- `agent_registry.json` is the authoritative source for agent IDs. When adding entries to
  `feedback_categories.yaml`'s `allowed_writers:` lists, cross-check against the `id`
  fields in `agent_registry.json`. Stale IDs cause silent validation failures in
  `submit_feedback.py`.
- `feedback_categories.yaml` uses a closed-list policy. The special writer value `hook`
  (not an agent ID) is introduced by ticket 09 (hook feedback emission) and reserved for
  commit_guardian hooks. Do not add new categories without a corresponding ADR or PR.
- `paths.json` is the source for the `## Project Paths` tables auto-injected into every
  built agent. After editing `paths.json`, run `leafcutter/scripts/build.py`
  to propagate changes.

## Maintenance

- To add a new agent: edit `agent_registry.json`, add the template, then run
  `build.py --validate` to confirm consistency.
- To add a new feedback category: edit `feedback_categories.yaml` via a PR, update
  `docs/how-to/feedback-collection.md` to reflect the new category, and update any
  agent signoff instructions that reference the category list.
- To add a new path constant: edit `paths.json`, then run `build.py` to rebuild all
  agents and skills.
