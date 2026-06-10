---
name: plan-feature
description: |
  Triage, orchestrate, and gate AC authoring for a user's feature request.
  Invokes the /plan-feature workflow (scripts/workflows/plan-feature.js): dispatches
  ac-triage to classify the request as strategic / behavioral / technical /
  covered, then routes through the correct authoring agents (PO v3, BA v3,
  IT PO v3) with user confirmation gates between stages. All output goes
  exclusively to the AC store (docs/acceptance-criteria/) — no ticket files
  are produced. The user sets priority at the final gate; the workflow writes
  readiness: approved on approval.
  Trigger phrases: "plan feature", "new AC", "author ACs",
  "write requirements", "/plan-feature".
allowed-tools: Bash, Read, Agent
workflow_script: scripts/workflows/plan-feature.js
---

# plan-feature skill

## Purpose

`/plan-feature` is the user-facing entry point to the AC authoring pipeline. It
wraps the `plan-feature.js` workflow script, which:

1. **Pre-triages** the user's request via the `ac-triage` agent (Haiku-tier)
   to check for duplicates and classify the routing path.
2. **Dispatches** the correct authoring agents in sequence based on the triage
   result, skipping upstream agents when the request only needs downstream work.
3. **Gates** each stage transition with user confirmation — the user sees the
   ACs produced at each stage and can approve, request edits, or cancel.
4. **Writes exclusively to the AC store** — no ticket files are produced.

## Invocation

```
/plan-feature <description> [--component <name>] [--force]
```

| Argument | Required | Description |
|---|---|---|
| `<description>` | Yes | Natural-language description of the feature or requirement. |
| `--component <name>` | No | Limit triage search to a specific component subdirectory (e.g. `--component inventory`). If omitted, all components are searched. |
| `--force` | No | Skip the duplicate check. Always creates new ACs even if existing ACs cover the request. Implicitly uses route: strategic. |

## Examples

```bash
# Author ACs for a new analytics dashboard (no existing L1 — strategic route)
/plan-feature "Allow users to export their dashboard as PDF" --component reports

# Author ACs for a behavioral addition to existing inventory feature
/plan-feature "Add sub-category filter to inventory list" --component inventory

# Force-create ACs even though the store has similar entries
/plan-feature "Inventory export as CSV" --component inventory --force

# Add a technical constraint to an existing feature
/plan-feature "Inventory API must respond in < 200ms for ≤10,000 items" --component inventory
```

## Routing Paths

| Route | When | Agents dispatched |
|---|---|---|
| `strategic` | No matching L1 AC found. New capability. | PO v3 → gate → BA v3 → gate → IT PO v3 → final gate |
| `behavioral` | Matching L1 AC found. Adding scenarios to existing feature. | BA v3 → gate → IT PO v3 → final gate |
| `technical` | Only adding technical constraints. | IT PO v3 → final gate |
| `covered` | Request fully covered by existing ACs. | Show existing ACs → user: cancel / amend / force |

## Gate Behaviour

At each gate, the user is shown the ACs produced by the previous agent and
offered three choices:

| Choice | Effect |
|---|---|
| `approve` | Proceeds to the next agent in the pipeline. |
| `edit` | Re-invokes the same agent with user-provided feedback (one retry). |
| `cancel` | Aborts the pipeline. ACs produced so far remain as `readiness: draft`. |

At the **final gate** (after IT PO v3), the user also sets the priority:
`critical`, `high`, `medium`, or `low`. Choosing `approve` + a priority sets
`readiness: approved` and `priority: <chosen>` on all ACs produced in the run.
Choosing `defer` leaves ACs as `readiness: reviewed` for a later approval run.

## Output

All AC files are written to:

```
docs/acceptance-criteria/<component>/<AC-ID>.yaml
```

Each AC file must pass `scripts/ac_store/validate_ac_schema.py` before the
workflow exits.

**No files are created in `tickets/`.** This workflow produces AC store entries
only; ticket generation from ACs is a separate concern handled by the
`/build-ac` command (AC scanner → ticket generator).

## Telemetry

The workflow logs each stage transition to `debugging/logs/agent_telemetry.jsonl`
via the `emit_event.py` script (non-blocking; failures are ignored).

## Error Handling

- If `ac-triage` returns unparseable JSON: the workflow exits with `status: error`
  and a descriptive message.
- If an authoring agent fails: the workflow retries once. If the retry fails,
  the pipeline aborts with `status: error`.
- If the AC store does not exist: triage defaults to route: strategic.

## Related

- `templates/agents/ac-triage.md` — Haiku-pinned triage agent.
- `scripts/workflows/plan-feature.js` — the underlying workflow script.
- `scripts/ac_store/validate_ac_schema.py` — AC YAML schema validator.
- `config/ac_schema.json` — JSON Schema for the triage output object.
- `/build-ac` — downstream command: scanner + ticket generator from existing ACs.
