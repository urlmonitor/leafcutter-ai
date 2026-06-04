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

## Schema enforcement

The `check_ac_schema.py` hook (installed by `build.py`) validates every
`.yaml` file under this directory against `config/ac_schema.json` on every
`git commit`. Schema violations block the commit.

See `docs/architecture/adrs/` for the ADR that introduced the AC store
(search for "ACTraceability").
