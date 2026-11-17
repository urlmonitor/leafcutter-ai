# retrospective scripts

Scripts used by the retrospective pipeline.

| Script | Purpose |
|--------|---------|
| `extract_epic_facts.py` | Extracts deterministic quantitative facts (ticket counts, phase agent stats, git commit count, blocker/handoff comment counts, telemetry events) from an epic folder. Outputs JSON to stdout for consumption by retrospective-agent. |

## Usage

```bash
python leafcutter/scripts/retrospective/extract_epic_facts.py tickets/99_done/EPIC-MyEpic/
python leafcutter/scripts/retrospective/extract_epic_facts.py tickets/00_inbox/epics/EPIC-MyEpic/ --telemetry "$(python3 leafcutter/scripts/knowledge/sink_resolution.py --print-location telemetry)"
```

Without `--telemetry`, the script reads the `operational_telemetry_stream`
declared in this install's `config/knowledge_sink.json` and refuses when no
usable declaration exists (INF-500d-4-v). The second line above names that same
declared stream explicitly through the side-effect-free location query.

## Output schema

See `extract_epic_facts.py` module docstring for the full JSON schema.
