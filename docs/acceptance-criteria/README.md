# Acceptance Criteria Store

This directory is the **AC store** — the canonical home for all acceptance
criteria (ACs) managed by this project.

## Directory structure

```
docs/acceptance-criteria/
├── index.yaml          # Component registry (this directory's manifest)
└── README.md           # This file
```

Individual AC files live in component subdirectories. For example:
```
docs/acceptance-criteria/
├── finalize/
│   ├── FIN-001.yaml
│   └── FIN-002.yaml
└── auth/
    └── AUTH-001.yaml
```

## Creating a new AC

1. Add the component to `index.yaml` (if it is a new component).
2. Create a subdirectory under `docs/acceptance-criteria/` matching the
   component `id` from `index.yaml`.
3. Write an AC YAML file following the schema defined in
   `config/ac_schema.json`. Name the file `<PREFIX>-NNN.yaml` where `NNN`
   is a zero-padded three-digit sequence number.

## Amending an existing AC

Edit the AC YAML file directly. The schema enforces required fields.
Run `check_ac_schema.py` to validate your changes before committing.

## Deprecating an AC

Add `status: deprecated` to the AC YAML file. Deprecated ACs are retained
for audit purposes but are excluded from active enforcement.

## Readiness lifecycle

Every AC YAML must carry a `readiness` field that controls whether the
scanner may pick it up for ticket generation:

| Readiness | Set by | Scanner picks up? |
|---|---|---|
| `draft` | product-owner-v3 or business-analyst-v3 | No |
| `reviewed` | it-po-v3 (after enrichment) | No |
| `approved` | User (via `/build-ac` or manual edit) | Yes |

New ACs are always created with `readiness: draft`. The scanner
(`scripts/ac_store/scan_ac_store.py`) silently ignores all ACs that are
not `readiness: approved`.

## Priority field

Every AC YAML must carry a `priority` field used by the scanner for
ranking. Valid values: `critical`, `high`, `medium`, `low`.

The scanner sorts ready ACs by priority first (critical → low), then by
`estimated_complexity` (S → XL) within the same priority tier. Users set
`priority` at approval time via manual edit.

## Backfill

Existing ACs authored before this field was introduced were backfilled
with `readiness: reviewed` and `priority: medium` by
`scripts/ac_store/backfill_readiness.py`. None of these will be picked up
by the scanner until the user promotes them to `readiness: approved`.

## Schema enforcement

The `validate_ac_schema.py` script (`scripts/ac_store/validate_ac_schema.py`)
validates every `.yaml` file under this directory, enforcing the required
`readiness` and `priority` fields on every `git commit`. Schema violations
block the commit.

See `docs/architecture/adrs/` for the ADR that introduced the AC store
(search for "ACTraceability").
