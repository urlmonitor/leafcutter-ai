# Ticket Prioritizer Scripts

## Purpose

This directory contains the Python scripts for the `ticket-prioritizer` skill.
`prioritize.py` parses YAML frontmatter from ticket `.md` files, builds a directed
acyclic dependency graph from `depends_on` fields, detects cycles, and surfaces only
unblocked tickets sorted by priority.

## Key Files

| File | Purpose |
|------|---------|
| `prioritize.py` | Core script: DAG construction, cycle detection, ready/blocked output |

## CLI Usage

```bash
# Scope to a single epic (sub-tickets only)
python .agents/skills/ticket-prioritizer/scripts/prioritize.py \
  --epic tickets/01_todo/EPIC-MyFeature/

# All tickets in 00_inbox and 01_todo (default)
python .agents/skills/ticket-prioritizer/scripts/prioritize.py --all

# JSON output for epic-supervisor
python .agents/skills/ticket-prioritizer/scripts/prioritize.py \
  --epic tickets/01_todo/EPIC-MyFeature/ --json
```

## Flags

| Flag | Description |
|------|-------------|
| `--epic PATH` | Scope to a single epic directory |
| `--all` | Scan tickets/00_inbox and tickets/01_todo (default) |
| `--json` | Emit machine-readable JSON instead of human-readable text |

## Done Detection

A ticket is considered done when:
- Its `status` frontmatter field equals `done` or `deferred`, OR
- It lives in a directory named `done/`, `99_done/`, or `99_rejected/`

## Cycle Detection

If a cycle is detected in `depends_on` chains, the script exits with code 1
and prints `CYCLE DETECTED: A -> B -> A` to stderr.

## Maintenance Notes

- `prioritize.py` is dependency-free (stdlib only) — no Poetry/pip requirements.
- All code changes must maintain the `DECISION HISTORY` block at the bottom.
