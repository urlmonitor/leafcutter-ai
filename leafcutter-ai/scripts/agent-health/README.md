# leafcutter/scripts/agent-health/

## Purpose

Agent health reporting scripts. These scripts join `agent_telemetry.jsonl` (invocation
volume and success rates) with `feedback.jsonl` (failure-mode classifications from
`subagent-quality` CFCS entries) to produce a per-agent quality table.

## Key Files

| File | Purpose |
|------|---------|
| `generate_health_report.py` | Joins telemetry and feedback into a per-agent markdown or JSON table. |

## Critical Context

- **Reads only** — these scripts never write to JSONL files.
- The `subagent-quality` CFCS category (added by EPIC-SupervisorFeedback) is the source
  for failure-mode archetypes. Scripts fail gracefully when the category has no entries.
- See `.claude/skills/agent-health/SKILL.md` for invocation patterns and output interpretation.

## Maintenance

- If the `agent_telemetry.jsonl` schema changes (new field names), update
  `_build_telemetry_table()` in `generate_health_report.py`.
- If new failure archetype tags are added to the CFCS `subagent-quality` category,
  update `ARCHETYPE_TAGS` in `generate_health_report.py`.
- Unit tests live in `unit_tests/feedback/test_generate_health_report.py`.
