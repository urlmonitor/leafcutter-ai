---
allowed-tools: Bash, Read
description: Wraps roadmap_query.py --audit to produce a structured audit_result
  JSON for the product-owner-agent. Use when you need to identify starved roadmap
  phases (no open tickets), off-roadmap open tickets, and a full phase inventory.
name: roadmap-steward
portable: true
---

# /roadmap-steward — Roadmap Audit Skill

## When to Use

- You are the product-owner-agent and need a structured audit of ticket-to-roadmap
  alignment before the PO dialogue.
- You want to identify phases with no active work (starved items).
- You want to identify open tickets that are not assigned to any roadmap phase
  (off-roadmap tickets).
- You need a single `audit_result` JSON payload that combines all three views.

## Invocation

```bash
# Full audit_result JSON — use this as the primary invocation
python portable-dev-workflow/scripts/roadmap_query.py --audit

# Individual views (optional — for debugging or targeted queries)
python portable-dev-workflow/scripts/roadmap_query.py --starved
python portable-dev-workflow/scripts/roadmap_query.py --off-roadmap
python portable-dev-workflow/scripts/roadmap_query.py --starved --format json
python portable-dev-workflow/scripts/roadmap_query.py --off-roadmap --format json
```

Add `--project-root <path>` when running from outside the project root.

## Output Contract — audit_result JSON

The `--audit` flag produces an `audit_result` JSON with this schema:

```json
{
  "all_items": [
    {
      "phase_id": "<string>",
      "title": "<string>",
      "outcome": "<string>",
      "status": "<active|planned|completed>"
    }
  ],
  "starved_items": [
    {
      "phase_id": "<string>",
      "title": "<string>",
      "outcome": "<string>"
    }
  ],
  "off_roadmap_tickets": [
    {
      "path": "<relative ticket path>",
      "title": "<string>"
    }
  ]
}
```

### Field Semantics

| Field | Meaning |
|-------|---------|
| `all_items` | Every phase in `docs/roadmap.json`, with id, title, description (→ outcome), and status |
| `starved_items` | Phases from `all_items` that have zero open tickets (`roadmap_phase` pointing to them, status: todo or in_progress) |
| `off_roadmap_tickets` | Open tickets (todo/in_progress) whose `roadmap_phase` field is absent or does not match any phase id in `docs/roadmap.json` |

## Usage Pattern for product-owner-agent

The product-owner-agent invokes this skill in Step 1 (Grounding) as follows:

1. Run `--audit` and capture the JSON output.
2. Parse `starved_items` — these are roadmap items with no active ticket.
3. Parse `off_roadmap_tickets` — these are open tickets not linked to the plan.
4. Combine with `docs/roadmap.json` fields (`current_phase`, `current_outcome`,
   `last_updated`) and `docs/vision.md` to produce the full audit presentation.

Example:

```bash
AUDIT=$(python portable-dev-workflow/scripts/roadmap_query.py --audit)
echo "$AUDIT"
```

Then parse the JSON in Python or pass it directly to the agent's reasoning step.

## Files Read

| File | Purpose |
|------|---------|
| `docs/roadmap.json` | Phase definitions, current_phase, current_outcome |
| `tickets/00_inbox/**/*.md` | Inbox tickets (scanned for roadmap_phase, status) |
| `tickets/01_todo/**/*.md` | Active tickets (scanned for roadmap_phase, status) |

`Master_Plan.md` and `README.md` are skipped automatically.
Done-ticket directories (`tickets/99_done/`, `done/` subfolders) are NOT scanned
— done tickets do not contribute to staleness or off-roadmap analysis.

## Error Behaviour

When `docs/roadmap.json` is absent:
```
ERROR: docs/roadmap.json not found.
Run `build.py` to create it from the template, or create it manually.
```

No Python traceback is shown. Exit code 1.
