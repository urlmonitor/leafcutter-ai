# retrospective scripts

Scripts used by the retrospective pipeline.

| Script | Purpose |
|--------|---------|
| `extract_epic_facts.py` | Extracts deterministic quantitative facts (ticket counts, phase agent stats, git commit count, blocker/handoff comment counts, telemetry events) from an epic folder. Outputs JSON to stdout for consumption by retrospective-agent. |

## Usage

```bash
python leafcutter/scripts/retrospective/extract_epic_facts.py tickets/99_done/EPIC-MyEpic/
python leafcutter/scripts/retrospective/extract_epic_facts.py tickets/00_inbox/epics/EPIC-MyEpic/ --telemetry debugging/logs/agent_telemetry.jsonl
```

## Output schema

See `extract_epic_facts.py` module docstring for the full JSON schema.
