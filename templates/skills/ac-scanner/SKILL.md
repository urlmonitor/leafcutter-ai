---
name: ac-scanner
description: |
  AC store scanner and ticket generator. Wraps two scripts:
  scan_ac_store.py (queries the AC YAML store for ready leaf-level ACs) and
  generate_ticket_from_ac.py (generates a fully-wired ticket file from a
  single AC YAML record and writes the implemented_by back-reference).
  Used by the /build-ac command (ticket 04) to drive the AC-first build loop.
allowed-tools: Bash, Read
---

# ac-scanner skill

## Purpose

Provide a machine-readable interface to the AC YAML store for the AC-driven
build pipeline. The skill wraps two scripts:

1. **`scan_ac_store.py`** — queries `docs/acceptance-criteria/` for leaf-level
   (L2/L3) ACs that are active, have `work_status: todo`, and have all
   `depends_on` references resolved (all deps have `work_status: done`). Returns
   a priority-sorted READY list and a BLOCKED list with blocking dep ids.

2. **`generate_ticket_from_ac.py`** — takes a single AC id, reads its YAML,
   and writes a fully-wired ticket file to `tickets/00_inbox/`. After writing,
   it appends the ticket path to the AC's `implemented_by` field to create a
   bidirectional traceability link.

Both scripts are idempotent and safe to re-run. The scanner never modifies the
store. The generator exits non-zero if a ticket for the same AC already exists.

---

## Invocation

### scan_ac_store.py

```bash
# Human-readable output (READY and BLOCKED sections)
python3 {{config.output_root}}/scripts/ac_store/scan_ac_store.py \
  --level leaf \
  --work-status todo

# JSON output for machine consumers (build-ac agent)
python3 {{config.output_root}}/scripts/ac_store/scan_ac_store.py \
  --level leaf \
  --work-status todo \
  --json

# Override the AC store root (useful for testing)
python3 {{config.output_root}}/scripts/ac_store/scan_ac_store.py \
  --level leaf \
  --work-status todo \
  --json \
  --ac-root /path/to/custom/ac-store/
```

**Flags:**

| Flag | Values | Default | Description |
|---|---|---|---|
| `--level` | `leaf`, `all` | `leaf` | `leaf` = L2/L3 only; `all` = all levels |
| `--work-status` | `todo`, `done`, `all` | `todo` | Filter by `work_status` field |
| `--json` | flag | off | Output JSON instead of human text |
| `--ac-root` | path | `docs/acceptance-criteria/` | Override the AC store root directory |

### generate_ticket_from_ac.py

```bash
# Generate a ticket from a specific AC id
python3 {{config.output_root}}/scripts/ac_store/generate_ticket_from_ac.py \
  --ac ACS-100a-1

# Dry-run: print ticket body without writing
python3 {{config.output_root}}/scripts/ac_store/generate_ticket_from_ac.py \
  --ac ACS-100a-1 \
  --dry-run

# Override roots (useful for testing or custom layouts)
python3 {{config.output_root}}/scripts/ac_store/generate_ticket_from_ac.py \
  --ac ACS-100a-1 \
  --ac-root /path/to/ac-store/ \
  --tickets-root /path/to/tickets/
```

**Flags:**

| Flag | Values | Default | Description |
|---|---|---|---|
| `--ac` | AC id string | (required) | The AC id to generate a ticket for |
| `--ac-root` | path | `docs/acceptance-criteria/` | Override the AC store root directory |
| `--tickets-root` | path | `tickets/00_inbox/` | Directory where the ticket file is written |
| `--dry-run` | flag | off | Print ticket body to stdout; do not write |

---

## Output Schema

### scan_ac_store.py — JSON (--json flag)

```json
{
  "ready": [
    {
      "ac_id": "ACS-100a-1",
      "title": "Required fields reject missing values at commit time",
      "assigned_agent": "python-coder",
      "estimated_complexity": "S",
      "path": "/abs/path/to/docs/acceptance-criteria/ac-store/ACS-100-structured-requirements/ACS-100a-1.yaml"
    }
  ],
  "blocked": [
    {
      "ac_id": "ACS-100b-3",
      "blocked_by": ["ACS-100b-1", "ACS-100b-2"]
    }
  ]
}
```

- `ready[*].ac_id` — the AC's `id` field value; every id resolves to an existing YAML file.
- `ready[*].path` — absolute filesystem path to the source YAML file.
- `blocked[*].blocked_by` — list of dep AC ids whose `work_status` is not `done`.

### scan_ac_store.py — Human-readable (default)

```
READY (3):
  [ S] ACS-100a-1                     Required fields reject missing values at commit time
  [ M] ACS-100b-2                     Feature folder naming follows PREFIX-NNN-kebab-slug convention
  [ L] ACS-200a-1                     Automated verification produces a structured report

BLOCKED (2):
  ACS-100b-3                          blocked by: ACS-100b-1, ACS-100b-2
  ACS-200b-1                          blocked by: ACS-200a-1
```

### generate_ticket_from_ac.py — on success (exit 0)

```
Written: /abs/path/to/tickets/00_inbox/TICKET-20260605-ACS-100a-1.md
```

The source AC YAML's `implemented_by` field is updated in-place with the relative
ticket path (targeted line replacement, not a full YAML round-trip).

---

## Error Codes

### scan_ac_store.py

| Exit code | Meaning | Stderr |
|---|---|---|
| `0` | Success (even when no ACs match — empty is valid) | (none) |
| `1` | One or more YAML files could not be read or parsed | Per-file diagnostic: `ERROR: <path>: <reason>` |
| `2` | Dependency cycle detected | `ERROR: dependency cycle detected: <id> → <id> → ...` |

### generate_ticket_from_ac.py

| Exit code | Meaning | Stderr |
|---|---|---|
| `0` | Ticket written (or dry-run completed) | (none) |
| `1` | AC id not found | `ERROR: AC id '<id>' not found under <ac-root>` |
| `1` | Ticket already exists (idempotency guard) | `ERROR: ticket for AC '<id>' already exists: <path>` |
| `1` | File I/O or YAML parse error | `ERROR: <context>: <reason>` |

---

## Integration with /build-ac (ticket 04)

The `/build-ac` command (not yet implemented — forward reference to epic ticket 04)
orchestrates the full AC-driven build loop:

```
scan_ac_store.py --json  →  ac_prioritizer.py --json  →  build-ac agent
    (READY list)              (top-ranked AC)              (proposes to user)
         ↓
generate_ticket_from_ac.py --ac <id>
    (writes ticket + implemented_by)
         ↓
/build-feature <ticket_path>
    (drives ticket through all phase agents)
         ↓
mark_ac_done.py --ticket <ticket_path>
    (sets work_status: done in source AC YAML)
```

The `ac-scanner` skill covers the first and third steps. The `ac_prioritizer.py`
script (ticket 02 of this epic) handles ranking. `mark_ac_done.py` (ticket 03)
handles the close-out write.

---

## Constraints

- `scan_ac_store.py` never modifies the AC store. It is read-only.
- `generate_ticket_from_ac.py` writes exactly two artifacts per invocation:
  the ticket file (new) and the `implemented_by` update in the source AC YAML
  (targeted append). It never modifies any other file.
- Both scripts are self-contained: they import only stdlib and PyYAML.
  No leafcutter-internal modules are imported.
- The `--dry-run` flag makes `generate_ticket_from_ac.py` completely
  non-destructive (no writes at all).

<!--
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-05 [ticket-01/llm-expert]: Initial authoring.
  Documents scan_ac_store.py (--level/--work-status/--json/--ac-root flags,
  JSON schema per AC-5, exit codes 0/1/2) and generate_ticket_from_ac.py
  (--ac/--ac-root/--tickets-root/--dry-run flags, exit codes 0/1).
  Includes forward reference to /build-ac (ticket 04) for pipeline context.
====================================================================
-->
