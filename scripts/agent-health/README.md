# leafcutter/scripts/agent-health/

## Purpose

Health reporting scripts, at two scopes. `generate_health_report.py` answers "how is
*this agent* doing?" by joining `agent_telemetry.jsonl` (invocation volume and success
rates) with `feedback.jsonl` (failure-mode classifications from `subagent-quality` CFCS
entries). `weekly_health.py` answers "how is *the system* doing, and are we speeding
up?" across whole weeks.

## Key Files

| File | Purpose |
|------|---------|
| `generate_health_report.py` | Joins telemetry and feedback into a per-agent markdown or JSON table. |
| `weekly_health.py` | Week-over-week delivery health: trust, autonomy, velocity, and code volume by language. |

## weekly_health.py

```bash
python scripts/agent-health/weekly_health.py --weeks 8
python scripts/agent-health/weekly_health.py --weeks 12 --format tsv > /tmp/health.tsv
python scripts/agent-health/weekly_health.py --no-gh            # offline; PR columns unknown
python scripts/agent-health/weekly_health.py --today 2026-08-26  # reproducible run
```

Metrics are sourced from git history, GitHub merge state, and reopen events rather than
from the AC store's own `work_status` field. That field has a documented phantom-done
history, so a report built on it would measure the rate at which the system produces
claims. A reopen is trusted precisely because it is a confession: the store only records
one against its own prior claim.

Three tiers print in dependency order — **trust** (reopen rate, known-issue drain,
repeat defects), **autonomy** (lane completion from the telemetry sink), **velocity**
(net verified criteria, feature share, code density, cycle time) — followed by a
code-volume breakdown by language. Read tier 1 first: while the reopen rate is high, the
tier-3 numbers are unverified.

**Unknown is never rendered as zero.** When the GitHub query fails, or its result page is
capped before reaching the oldest reporting week, PR columns read `—` in Markdown and
empty in TSV, with a `prs_available` column carrying the fact. When the telemetry sink
holds no lane-run events, the autonomy section names the reason rather than printing a 0%
completion rate — an unwired emitter and a lane that fails every run are different facts
(KI-BO-012).

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
- Unit tests live in `unit_tests/feedback/test_generate_health_report.py` and
  `unit_tests/agent_health/test_weekly_health.py`.
- `weekly_health.py` reuses `build_lane_comparison_report` from
  `generate_health_report.py` rather than re-reading the sink, so the two reports cannot
  disagree about the same file. Keep that import if the lane schema changes.
- The lane-event vocabularies (`_LANE_START_EVENTS`, `_LANE_SUCCESS_EVENTS`,
  `_LANE_HALT_EVENTS` in `weekly_health.py`) are provisional — nothing has ever emitted a
  lane event, so they could not be verified against real data. When the fast lane starts
  emitting, confirm they match what it writes; if they drift, the autonomy tier will
  report "no lane data" while events are arriving.
